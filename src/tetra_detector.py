#!/usr/bin/env python3
"""
Tetra Signal Detector - Multi-SDR Support
Detecteert RF signalen met ondersteuning voor meerdere RTL-SDR devices
"""

import time
from datetime import datetime
import sys
import signal
from pathlib import Path
from typing import Dict, Any, List

from config_loader import ConfigLoader
from sdr_manager import SDRManager

class TetraDetector:
    """Main detector class met multi-SDR support"""
    
    def __init__(self, config_path: str = 'configs/config.yml', demo_mode: bool = False):
        self.config = ConfigLoader.load(config_path)
        self.demo_mode = demo_mode
        self.sdr_manager = SDRManager(self.config, demo_mode)
        self.detection_counts = {}  # Per device
        self.total_detections = 0
        self.running = True
        self.log_file = None
        
        # Initialize detection counters
        for i in range(self.sdr_manager.get_device_count()):
            self.detection_counts[i] = 0
        
        # Setup logging
        if self.config['logging']['enabled']:
            self.setup_logging()
    
    def setup_logging(self):
        """Setup logging naar file"""
        log_dir = Path(self.config['logging']['directory'])
        log_dir.mkdir(exist_ok=True)
        
        filename = datetime.now().strftime(self.config['logging']['filename_format'])
        log_path = log_dir / filename
        
        self.log_file = open(log_path, 'a')
        self.log(f"=== Tetra Detector gestart om {datetime.now()} ===")
        
        # Log device info
        for device_info in self.sdr_manager.get_devices_info():
            self.log(f"Device #{device_info['index']}: {device_info['name']} @ {device_info['frequency']} MHz ({device_info['mode']})")
        
        self.log(f"Threshold: {self.config['detection']['threshold']} dBm")
        print(f"✓ Logging naar: {log_path}")
    
    def log(self, message: str):
        """Log message naar file"""
        if self.log_file:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_file.write(f"[{timestamp}] {message}\n")
            self.log_file.flush()
    
    def create_bar(self, value: float, max_value: float = 100) -> str:
        """Maak text-based progress bar"""
        width = self.config['display']['bar_width']
        percentage = min(100, max(0, (value / max_value) * 100))
        filled = int((percentage / 100) * width)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}] {percentage:.0f}%"
    
    def normalize_power(self, power_db: float) -> float:
        """Normaliseer power naar 0-100%"""
        min_db = self.config['display']['power_range_min']
        max_db = self.config['display']['power_range_max']
        normalized = ((power_db - min_db) / (max_db - min_db)) * 100
        return max(0, min(100, normalized))
    
    def display_status(self, results: List[Dict[str, Any]]):
        """Toon status in CLI voor alle devices"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        use_colors = self.config['display']['use_colors']
        
        if use_colors:
            reset = "\033[0m"
            green = "\033[92m"
            red = "\033[91m"
            yellow = "\033[93m"
        else:
            reset = green = red = yellow = ""
        
        # Clear line
        print(f"\r{' ' * 120}\r", end='')
        
        if self.sdr_manager.is_multi_device():
            # Multi-device display
            print(f"\r{yellow}{timestamp}{reset}", end='')
            
            for result in results:
                normalized = self.normalize_power(result['power_db'])
                bar = self.create_bar(normalized, 100)
                
                color = red if result['detected'] else green
                status = "🚨" if result['detected'] else "🔍"
                
                device_name = result['device_name'][:12]  # Truncate lange namen
                count = self.detection_counts[result['device_index']]
                
                print(f" | {color}{status}{reset} {device_name}: {bar} {result['power_db']:.1f}dBm ({count})", end='')
        else:
            # Single device display
            result = results[0]
            normalized = self.normalize_power(result['power_db'])
            bar = self.create_bar(normalized, 100)
            
            color = red if result['detected'] else green
            status = "🚨 DETECTIE!" if result['detected'] else "🔍 Scanning..."
            
            print(f"\r{color}{timestamp}{reset} | {bar} | {result['power_db']:.1f} dBm | {status} | Count: {self.total_detections}", end='')
        
        sys.stdout.flush()
    
    def print_header(self):
        """Print header met device info"""
        print("\n" + "="*100)
        print("  TETRA DETECTOR - Multi-SDR RF Signal Monitor")
        print("="*100)
        
        devices_info = self.sdr_manager.get_devices_info()
        
        if len(devices_info) > 1:
            print(f"  Devices: {len(devices_info)} RTL-SDR dongles")
        else:
            print(f"  Device: Single RTL-SDR")
        
        for info in devices_info:
            mode_str = f"({info['mode']})"
            print(f"    [{info['index']}] {info['name']}: {info['frequency']} MHz @ {info['sample_rate']} MS/s {mode_str}")
        
        print(f"  Threshold: {self.config['detection']['threshold']} dBm")
        print("="*100 + "\n")
        print("Druk Ctrl+C om te stoppen\n")
    
    def run(self):
        """Main detection loop"""
        self.print_header()
        
        try:
            while self.running:
                # Scan alle devices
                results = self.sdr_manager.scan_all(self.config['detection']['samples'])
                
                # Check voor detecties
                for result in results:
                    if result['detected']:
                        self.detection_counts[result['device_index']] += 1
                        self.total_detections += 1
                        
                        # Log detectie
                        # print()  # Nieuwe regel
                        # msg = (f"⚠️  [{datetime.now().strftime('%H:%M:%S')}] "
                        #       f"{result['device_name']}: Signaal gedetecteerd op "
                        #       f"{result['frequency']:.2f} MHz @ {result['power_db']:.1f} dBm")
                        # print(msg)
                        # self.log(msg)
                
                # Display status
                self.display_status(results)
                
                # Sleep
                time.sleep(self.config['detection']['scan_interval'])
                
        except KeyboardInterrupt:
            print("\n\n✓ Detector gestopt")
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        self.sdr_manager.close_all()
        
        print(f"\nTotaal detecties: {self.total_detections}")
        
        if self.sdr_manager.is_multi_device():
            print("\nPer device:")
            for idx, count in self.detection_counts.items():
                devices = self.sdr_manager.get_devices_info()
                name = devices[idx]['name'] if idx < len(devices) else f"Device {idx}"
                print(f"  {name}: {count}")
        
        self.log(f"Detector gestopt. Totaal detecties: {self.total_detections}")
        
        if self.log_file:
            self.log_file.close()

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\nStoppen...")
    sys.exit(0)

def main():
    """Main entry point"""
    signal.signal(signal.SIGINT, signal_handler)
    
    # Parse argumenten
    config_path = 'configs/config.yml'
    demo = '--demo' in sys.argv
    
    for arg in sys.argv[1:]:
        if arg.startswith('--config='):
            config_path = arg.split('=')[1]
    
    # Start detector
    detector = TetraDetector(config_path=config_path, demo_mode=demo)
    detector.run()

if __name__ == "__main__":
    main()