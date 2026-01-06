"""
Config Loader voor Tetra Detector
"""

import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigLoader:
    """Laadt en valideert configuratie files"""
    
    @staticmethod
    def load(config_path: str) -> Dict[str, Any]:
        """Laad configuratie uit YAML file"""
        path = Path(config_path)
        
        if not path.exists():
            print(f"⚠️  Config file niet gevonden: {config_path}")
            print("   Gebruik default configuratie")
            return ConfigLoader.default_config()
        
        try:
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            print(f"✓ Configuratie geladen uit {config_path}")
            
            # Valideer en vul ontbrekende waarden aan
            return ConfigLoader.validate_config(config)
        except Exception as e:
            print(f"❌ Error bij laden config: {e}")
            return ConfigLoader.default_config()
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Valideer en vul configuratie aan met defaults"""
        defaults = ConfigLoader.default_config()
        
        # Merge met defaults
        for section in defaults:
            if section not in config:
                config[section] = defaults[section]
            else:
                # Merge subsections
                for key in defaults[section]:
                    if key not in config[section]:
                        config[section][key] = defaults[section][key]
        
        return config
    
    @staticmethod
    def default_config() -> Dict[str, Any]:
        """Default configuratie"""
        return {
            'sdr': {
                'mode': 'single',  # 'single' of 'multi'
                'devices': [
                    {
                        'index': 0,
                        'center_frequency': 382.5,
                        'sample_rate': 2.4,
                        'gain': 'auto',
                        'ppm_correction': 0,
                        'name': 'Tetra Mobile'
                    }
                ]
            },
            'detection': {
                'threshold': -50,
                'scan_interval': 0.5,
                'samples': 262144
            },
            'display': {
                'bar_width': 30,
                'power_range_min': -80,
                'power_range_max': -20,
                'use_colors': True,
                'show_device_names': True
            },
            'logging': {
                'enabled': True,
                'directory': './logs',
                'filename_format': 'tetra_detector_%Y%m%d.log',
                'level': 'INFO'
            }
        }
    
    @staticmethod
    def get_device_config(config: Dict[str, Any], device_index: int) -> Dict[str, Any]:
        """Haal configuratie op voor specifiek device"""
        devices = config.get('sdr', {}).get('devices', [])
        
        if device_index < len(devices):
            return devices[device_index]
        
        # Return default device config
        return ConfigLoader.default_config()['sdr']['devices'][0]