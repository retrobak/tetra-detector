"""
SDR Manager voor Multi-Device Support
"""

import numpy as np
from typing import List, Dict, Optional, Any
import threading
import time

try:
    from rtlsdr import RtlSdr
    RTL_AVAILABLE = True
except ImportError:
    RTL_AVAILABLE = False

class SDRDevice:
    """Wrapper voor een enkele RTL-SDR device"""
    
    def __init__(self, device_config: Dict[str, Any], demo_mode: bool = False):
        self.config = device_config
        self.demo_mode = demo_mode
        self.sdr = None
        self.last_power_db = -80
        self.lock = threading.Lock()
        
        if not demo_mode and RTL_AVAILABLE:
            self.initialize()
    
    def initialize(self):
        """Initialiseer RTL-SDR device"""
        try:
            self.sdr = RtlSdr(self.config['index'])
            self.configure()
            print(f"✓ SDR #{self.config['index']} ({self.config['name']}) geïnitialiseerd")
        except Exception as e:
            print(f"❌ Fout bij initialiseren SDR #{self.config['index']}: {e}")
            self.demo_mode = True
    
    def configure(self):
        """Configureer SDR met instellingen"""
        if not self.sdr:
            return
        
        # Calculate frequency with PPM correction applied
        base_freq = self.config['center_frequency'] * 1e6
        ppm = self.config.get('ppm_correction', 0)
        
        # Apply PPM correction to frequency (ppm = parts per million)
        # Negative PPM means tuner is too low, so we tune higher
        corrected_freq = base_freq * (1 + ppm / 1e6)
        
        self.sdr.center_freq = corrected_freq
        self.sdr.sample_rate = self.config['sample_rate'] * 1e6
        self.sdr.gain = self.config['gain']
        
        # Don't try to set freq_correction as this device doesn't support it
    
    def scan(self, samples: int = 262144) -> float:
        """Scan frequentie en return power in dBm"""
        with self.lock:
            if self.demo_mode or not self.sdr:
                # Demo mode - simuleer signaal
                base = np.random.uniform(-70, -60)
                if np.random.random() > 0.85:
                    self.last_power_db = np.random.uniform(-45, -35)
                else:
                    self.last_power_db = base
            else:
                try:
                    data = self.sdr.read_samples(samples)
                    power = np.mean(np.abs(data)**2)
                    # Convert to dBm with proper reference level
                    # RTL-SDR gives normalized values, typical reference is around -50 dBFS = -50 dBm
                    power_db = 10 * np.log10(power + 1e-10)
                    self.last_power_db = power_db - 50  # Adjust to approximate dBm scale
                except Exception as e:
                    print(f"\n❌ Fout bij scannen SDR #{self.config['index']}: {e}")
                    self.last_power_db = -80
            
            return self.last_power_db
    
    def get_info(self) -> Dict[str, Any]:
        """Haal device info op"""
        return {
            'index': self.config['index'],
            'name': self.config['name'],
            'frequency': self.config['center_frequency'],
            'sample_rate': self.config['sample_rate'],
            'gain': self.config['gain'],
            'mode': 'DEMO' if self.demo_mode else 'LIVE'
        }
    
    def close(self):
        """Sluit SDR device"""
        if self.sdr:
            try:
                self.sdr.close()
            except:
                pass

class SDRManager:
    """Manager voor meerdere SDR devices"""
    
    def __init__(self, config: Dict[str, Any], demo_mode: bool = False):
        self.config = config
        self.demo_mode = demo_mode or not RTL_AVAILABLE
        self.devices: List[SDRDevice] = []
        self.scan_threads: List[threading.Thread] = []
        self.running = False
        
        self.initialize_devices()
    
    def initialize_devices(self):
        """Initialiseer alle SDR devices"""
        device_configs = self.config['sdr']['devices']
        
        print(f"\nInitialiseren van {len(device_configs)} SDR device(s)...")
        
        for device_config in device_configs:
            device = SDRDevice(device_config, self.demo_mode)
            self.devices.append(device)
        
        if self.demo_mode:
            print("⚠️  RTL-SDR niet beschikbaar, gebruik DEMO modus")
    
    def scan_all(self, samples: int = 262144) -> List[Dict[str, Any]]:
        """Scan alle devices en return resultaten"""
        results = []
        
        for device in self.devices:
            power_db = device.scan(samples)
            results.append({
                'device_index': device.config['index'],
                'device_name': device.config['name'],
                'frequency': device.config['center_frequency'],
                'power_db': power_db,
                'detected': power_db > self.config['detection']['threshold']
            })
        
        return results
    
    def get_devices_info(self) -> List[Dict[str, Any]]:
        """Haal info op van alle devices"""
        return [device.get_info() for device in self.devices]
    
    def get_device_count(self) -> int:
        """Return aantal devices"""
        return len(self.devices)
    
    def is_multi_device(self) -> bool:
        """Check of we meerdere devices gebruiken"""
        return len(self.devices) > 1
    
    def close_all(self):
        """Sluit alle SDR devices"""
        for device in self.devices:
            device.close()