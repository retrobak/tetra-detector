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
from collections import deque
import numpy as np

from config_loader import ConfigLoader
from sdr_manager import SDRManager
from colorama import Fore, Back, Style, init

class TetraDetector:
    """Main detector class met multi-SDR support"""
    
    def __init__(self, config_path: str = 'configs/config.yml', demo_mode: bool = False):
        self.config = ConfigLoader.load(config_path)
        init()
        self.demo_mode = demo_mode
        self.sdr_manager = SDRManager(self.config, demo_mode)
        self.detection_counts = {}  # Per device
        self.total_detections = 0
        self.running = True
        self.log_file = None
        self.display_initialized = False
        
        # Adaptive threshold tracking
        self.noise_floor_history = {}  # Per device: deque of recent power readings
        self.noise_floor = {}  # Per device: calculated noise floor
        self.dynamic_threshold = {}  # Per device: dynamic detection threshold
        
        # Pulse window tracking for pulsed signals
        self.pulse_window_seconds = self.config['detection'].get('pulse_window_seconds', 4.0)
        self.signal_history = {}  # Per device: deque of (timestamp, power_db) tuples
        self.peak_in_window = {}  # Per device: peak signal strength in window
        self.previous_peak = {}  # Per device: previous peak for trend detection
        self.last_detection_peak = {}  # Per device: peak from last detection window
        self.last_detection_time = {}  # Per device: timestamp of last detection
        
        # Initialize detection counters and adaptive tracking
        adaptive_config = self.config['detection'].get('adaptive', {})
        self.adaptive_enabled = adaptive_config.get('enabled', False)
        self.noise_floor_window = adaptive_config.get('noise_floor_window', 20)
        self.threshold_margin = adaptive_config.get('threshold_margin', 8)
        
        # Display configuration
        display_config = self.config.get('display', {})
        self.show_debug_info = display_config.get('show_debug_info', True)
        
        for i in range(self.sdr_manager.get_device_count()):
            self.detection_counts[i] = 0
            self.noise_floor_history[i] = deque(maxlen=self.noise_floor_window)
            self.noise_floor[i] = None
            self.dynamic_threshold[i] = self.config['detection']['threshold']
            self.signal_history[i] = deque()  # No maxlen - we'll trim by time
            self.peak_in_window[i] = -100.0  # Start with very low value
            self.previous_peak[i] = -100.0
            self.last_detection_peak[i] = -100.0  # Start with very low value
            self.last_detection_time[i] = None  # No detection yet
        
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
        """Toon status in CLI voor alle devices - fixed position display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        use_colors = self.config['display']['use_colors']
        
        detected_any = any(result['detected'] for result in results)
        
        if use_colors:
            reset = Style.RESET_ALL
            green = Fore.GREEN
            red = Fore.RED
            yellow = Fore.YELLOW
            cyan = Fore.CYAN
            dim = Style.DIM
        else:
            reset = green = red = yellow = cyan = dim = ""
        
        devices_info = self.sdr_manager.get_devices_info()
        is_multi = self.sdr_manager.is_multi_device()
        
        # Calculate number of lines needed
        lines_needed = 6  # Fixed layout: header(3) + status(2) + bottom border(1)
        if self.show_debug_info:
            lines_needed += 6  # Debug section: header(2) + table header(2) + device rows + bottom border(1)
            if is_multi:
                lines_needed += 1  # Extra line for second device
        
        # Clear screen and move to top if display was initialized
        if self.display_initialized:
            print("\033[2J\033[H", end='')  # Clear screen and move cursor to top
        
        # Main display - show signal from last detection/pulse window
        main_result = results[0]
        
        # Check if last detection is still valid (within pulse_window + 1 second)
        current_time = time.time()
        reset_timeout = self.pulse_window_seconds + 1.0
        
        if (self.last_detection_time[0] is not None and 
            self.last_detection_peak[0] > -90 and 
            current_time - self.last_detection_time[0] <= reset_timeout):
            # Valid recent detection
            display_power = self.last_detection_peak[0]
            display_label = "Last Detection"
        else:
            # No recent detection or timed out - show noise floor or default
            if self.noise_floor[0] is not None:
                display_power = self.noise_floor[0]  # Use established noise floor
            else:
                display_power = -80.0  # Default baseline when no noise floor established
            display_label = "No Signal"
        
        normalized = self.normalize_power(display_power)
        bar = self.create_bar(normalized, 100)
        bar_color = red if detected_any else green
        
        # Status text
        status_text = "DETECTING!" if detected_any else display_label
        status_color = red if detected_any else green
        
        # Build display
        print(f"\033[2K{cyan}{'═'*63}{reset}")
        print(f"\033[2K{cyan} {reset} │ {timestamp} │ {status_color}{status_text}{reset}")
        print(f"\033[2K{cyan}{'═'*63}{reset}")
        print(f"\033[2K")
        print(f"\033[2K{bar_color}  {bar}  {display_power:>6.1f} dBm{reset}")
        print(f"\033[2K")
        
        # Debug information section (conditional)
        if self.show_debug_info:
            print(f"\033[2K{cyan}{'═'*63}{reset}")
            print(f"\033[2K{cyan}  Debug information:{reset}")
            print(f"\033[2K{cyan}{'═'*63}{reset}")
            
            # Table header
            print(f"\033[2K   {dim}│{reset} Current   {dim}│{reset} Peak     {dim}│{reset} Gain {dim}│{reset}    NF  {dim}│{reset} Threshold")
            print(f"\033[2K{dim}───╬───────────┼──────────┼──────┼────────┼────────────────{reset}")
            
            # Table rows - one per device
            for result in results:
                device_idx = result['device_index']
                peak = self.peak_in_window[device_idx]
                prev_peak = self.previous_peak[device_idx]
                trend = "↑" if peak > prev_peak + 1 else "↓" if peak < prev_peak - 1 else "─"
                
                gain = str(devices_info[device_idx]['gain']).ljust(4)
                
                # Color the row if this device detected
                row_color = red if result['detected'] else ""
                
                nf_str = f"{result['noise_floor']:>6.1f}" if result.get('noise_floor') is not None else "    --"
                thr_str = f"{result['threshold']:>6.1f}" if result.get('threshold') is not None else "    --"
                
                print(f"\033[2K{row_color}#{device_idx+1} {dim}│{reset} {result['power_db']:>6.1f} dBm {dim}│{reset} {peak:>6.1f} {trend} {dim}│{reset} {gain} {dim}│{reset} {nf_str} {dim}│{reset} {thr_str}{reset}")
            
            print(f"\033[2K{cyan}{'═'*63}{reset}")
        else:
            print(f"\033[2K{cyan}{'═'*63}{reset}")
        
        sys.stdout.flush()
        self.display_initialized = True
    
    def print_header(self):
        """Print header met device info"""
        print("\n" + "="*100)
        print("  Multi-SDR RF Signal Monitor")
        print("="*100)
        
        devices_info = self.sdr_manager.get_devices_info()
        
        if len(devices_info) > 1:
            print(f"  Devices: {len(devices_info)} RTL-SDR dongles")
        else:
            print(f"  Device: Single RTL-SDR")
        
        for info in devices_info:
            mode_str = f"({info['mode']})"
            print(f"    [{info['index']}] {info['name']}: {info['frequency']} MHz @ {info['sample_rate']} MS/s {mode_str}")
        
        if self.adaptive_enabled:
            print(f"  Threshold: ADAPTIVE (margin: +{self.threshold_margin} dBm from noise floor)")
        else:
            print(f"  Threshold: {self.config['detection']['threshold']} dBm (FIXED)")
        print("="*100 + "\n")
        print("Druk Ctrl+C om te stoppen\n")
    
    def update_noise_floor(self, device_index: int, power_db: float, is_signal: bool = False):
        """Update noise floor calculation for a device"""
        if not self.adaptive_enabled:
            return
        
        # Only add to noise floor history if it's not a detected signal
        if not is_signal:
            self.noise_floor_history[device_index].append(power_db)
        
        # Calculate noise floor from recent non-signal readings
        if len(self.noise_floor_history[device_index]) >= 5:
            # Use median to be robust against outliers
            self.noise_floor[device_index] = np.median(list(self.noise_floor_history[device_index]))
            # Set dynamic threshold: noise floor + margin
            self.dynamic_threshold[device_index] = self.noise_floor[device_index] + self.threshold_margin
    
    def update_pulse_window(self, device_index: int, power_db: float):
        """Update signal history and track peak signal in time window"""
        current_time = time.time()
        
        # Add current reading to history
        self.signal_history[device_index].append((current_time, power_db))
        
        # Remove old readings outside the pulse window
        cutoff_time = current_time - self.pulse_window_seconds
        while self.signal_history[device_index] and self.signal_history[device_index][0][0] < cutoff_time:
            self.signal_history[device_index].popleft()
        
        # Calculate peak signal in the window
        if self.signal_history[device_index]:
            self.previous_peak[device_index] = self.peak_in_window[device_index]
            self.peak_in_window[device_index] = max(
                reading[1] for reading in self.signal_history[device_index]
            )
        else:
            self.peak_in_window[device_index] = power_db
    
    def run(self):
        """Main detection loop"""
        self.print_header()
        
        try:
            while self.running:
                # Scan alle devices
                results = self.sdr_manager.scan_all(self.config['detection']['samples'])
                
                # Update noise floor and check for detections
                for result in results:
                    device_idx = result['device_index']
                    
                    # For adaptive mode, use dynamic threshold
                    if self.adaptive_enabled and self.noise_floor[device_idx] is not None:
                        result['threshold'] = self.dynamic_threshold[device_idx]
                        result['detected'] = result['power_db'] > self.dynamic_threshold[device_idx]
                        result['noise_floor'] = self.noise_floor[device_idx]
                    else:
                        result['threshold'] = self.config['detection']['threshold']
                        result['noise_floor'] = None
                    
                    # Update noise floor tracking
                    self.update_noise_floor(device_idx, result['power_db'], result['detected'])
                    
                    # Update pulse window tracking
                    self.update_pulse_window(device_idx, result['power_db'])
                    
                    if result['detected']:
                        self.detection_counts[device_idx] += 1
                        self.total_detections += 1
                        
                        # Store the peak from this detection window
                        self.last_detection_peak[device_idx] = self.peak_in_window[device_idx]
                        # Record the timestamp of this detection
                        self.last_detection_time[device_idx] = time.time()
                        
                        # Log detectie (to file only, no console print)
                        msg = (f"⚠️  [{datetime.now().strftime('%H:%M:%S')}] "
                              f"{result['device_name']}: Signaal gedetecteerd op "
                              f"{result['frequency']:.2f} MHz @ {result['power_db']:.1f} dBm")
                        if self.adaptive_enabled and result['noise_floor'] is not None:
                            msg += f" (noise floor: {result['noise_floor']:.1f} dBm, threshold: {result['threshold']:.1f} dBm)"
                        self.log(msg)
                
                # Display status
                self.display_status(results)
                
                # Sleep
                time.sleep(self.config['detection']['scan_interval'])
                
        except KeyboardInterrupt:
            self.cleanup()
            print("\n✓ Detector gestopt")
    
    def cleanup(self):
        """Cleanup resources"""
        self.sdr_manager.close_all()
        
        print(f"Totaal detecties: {self.total_detections}")
        
        if self.sdr_manager.is_multi_device():
            print("Per device:")
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