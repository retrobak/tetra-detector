# 🔍 Tetra Detector - Multi-SDR RF Signal Monitor

Een professionele detector voor Tetra signalen (380-395 MHz) met ondersteuning voor meerdere RTL-SDR dongles en CLI visualisatie.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Docker](https://img.shields.io/badge/docker-ready-brightgreen)

## 📋 Features

- ✅ **Multi-SDR Support** - Gebruik meerdere RTL-SDR dongles tegelijk
- ✅ **Real-time CLI Visualisatie** - Text-based progress bars en live updates
- ✅ **Flexible Configuration** - YAML config files voor verschillende scenarios
- ✅ **Auto Logging** - Detecties worden automatisch gelogd met timestamps
- ✅ **FM Calibratie Mode** - Bepaal PPM offset met bekende FM frequenties
- ✅ **Docker Ready** - Volledig containerized met Docker Compose
- ✅ **Demo Mode** - Test zonder hardware

## 🛠️ Hardware

### Minimaal (Single SDR)
- 1x RTL-SDR dongle (RTL2832U chipset)
- Antenne voor ~380 MHz (1/4 wave = ~19 cm)
- Raspberry Pi Zero 2 W of andere Linux machine

### Optimaal (Dual SDR)
- 2x RTL-SDR dongle
- 2x Antenne (één voor mobiel, één voor base stations)
- Raspberry Pi 4 of desktop computer

**Let op**: Goedkope RTL-SDR dongles hebben een maximum bandwidth van ~2.4 MHz. Voor volledige Tetra coverage (5 MHz breed) zijn twee dongles nodig.

## 🚀 Quick Start

### 1. Auto Setup (Aanbevolen)

```bash
# Download project files
git clone <repo-url>
cd tetra-detector

# Maak setup script executable
chmod +x setup.sh

# Run setup script
./setup.sh
```

Het script bouwt automatisch de Docker image en vraagt wat je wilt doen.

### 2. Manuele Setup

```bash
# Installeer Docker (indien nodig)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Log uit en weer in

# Build Docker image
docker-compose build

# Start detector
docker-compose up tetra-detector
```

## 📁 Project Structuur

```
tetra-detector/
│
├── src/                           # Source code
│   ├── __init__.py
│   ├── tetra_detector.py         # Main detector
│   ├── sdr_manager.py            # Multi-SDR management
│   └── config_loader.py          # Config utilities
│
├── configs/                       # Configuratie files
│   ├── config.yml                # Default (single SDR mobile)
│   ├── dual_sdr.yml              # Dual SDR setup
│   ├── single_sdr_mobile.yml    # Mobiele band only
│   ├── single_sdr_base.yml      # Base stations only
│   └── fm_calibration.yml        # FM calibratie
│
├── logs/                          # Auto-generated logs
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── setup.sh                       # Auto setup script
└── README.md
```

## 🎛️ Configuratie

### Single SDR - Tetra Mobile (Default)

```yaml
# configs/config.yml
sdr:
  devices:
    - index: 0
      name: "Tetra Mobile"
      center_frequency: 382.5  # MHz
      sample_rate: 2.4
      ppm_correction: 0

detection:
  threshold: -50  # dBm
```

**Dekt**: ~381.3 - 383.7 MHz (belangrijkste deel van mobiele band)

### Dual SDR - Volledige Coverage

```yaml
# configs/dual_sdr.yml
sdr:
  devices:
    - index: 0
      name: "Tetra Mobile"
      center_frequency: 382.5
    - index: 1
      name: "Tetra Base"
      center_frequency: 392.5
```

Start met: `docker-compose --profile dual up`

**Dekt**: Beide banden (mobiel + base stations)

### FM Calibratie - PPM Offset Bepalen

```yaml
# configs/fm_calibration.yml
sdr:
  devices:
    - index: 0
      center_frequency: 100.7  # NPO Radio 1
      ppm_correction: 0  # Pas aan tot signaal exact klopt
```

Start met: `docker-compose --profile calibrate up`

**Workflow**:
1. Start FM calibratie mode
2. Kijk of signaal precies op 100.7 MHz zit
3. Pas `ppm_correction` aan (bijv. -10 of +10)
4. Herhaal tot exact
5. Gebruik gevonden waarde in Tetra config

## 🖥️ Gebruik

### Basic Commands

```bash
# Single SDR (default)
docker-compose up tetra-detector

# Dual SDR
docker-compose --profile dual up tetra-dual

# FM Calibratie
docker-compose --profile calibrate up fm-calibration

# Demo mode (zonder hardware)
docker-compose --profile demo up demo

# Stop met Ctrl+C
```

### CLI Output

**Single SDR:**
```
14:23:45 | [████████░░░░░░░░░░░░] 45% | -62.3 dBm | 🔍 Scanning... | Count: 0
```

**Dual SDR:**
```
14:23:45 | 🔍 Tetra Mobile: [████░░░░] 32% -65.1dBm (0) | 🚨 Tetra Base: [████████] 78% -42.3dBm (3)
```

**Bij detectie:**
```
⚠️  [14:25:12] Tetra Mobile: Signaal gedetecteerd op 382.50 MHz @ -42.1 dBm
```

## 🔧 Advanced

### Custom Config

```bash
# Gebruik eigen config file
docker run -it \
  --privileged \
  --device /dev/bus/usb \
  -v $(pwd)/my_config.yml:/app/configs/my_config.yml \
  tetra-detector \
  python tetra_detector.py --config=/app/configs/my_config.yml
```

### Direct Python (zonder Docker)

```bash
# Installeer dependencies
pip install -r requirements.txt

# Installeer RTL-SDR drivers
sudo apt-get install rtl-sdr librtlsdr-dev

# Run
cd src
python tetra_detector.py --config=../configs/config.yml
```

### Logging

Logs worden automatisch opgeslagen in `./logs/`:
```
logs/
├── tetra_detector_20260106.log
├── tetra_dual_20260106.log
└── fm_calibration_20260106.log
```

### Meerdere Configuraties Switchen

```bash
# Maak eigen configs
cp configs/config.yml configs/my_location.yml

# Edit my_location.yml met jouw settings

# Start met custom config
docker run -it \
  -v $(pwd)/configs:/app/configs \
  tetra-detector \
  python tetra_detector.py --config=/app/configs/my_location.yml
```

## 🐛 Troubleshooting

### RTL-SDR niet gevonden

```bash
# Check USB devices
lsusb | grep RTL

# Check permissions
sudo usermod -aG plugdev $USER

# Udev rule toevoegen
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", MODE="0666"' | \
  sudo tee /etc/udev/rules.d/20-rtlsdr.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Dual SDR - Device index bepalen

```bash
# List alle RTL-SDR devices
rtl_test

# Output toont device indices:
# Found 2 device(s):
#   0:  Realtek, RTL2838UHIDIR, SN: 00000001
#   1:  Realtek, RTL2838UHIDIR, SN: 00000002
```

### Docker permissie problemen

```bash
# Rebuild zonder cache
docker-compose build --no-cache

# Check Docker logs
docker-compose logs
```

### Signaal te zwak

```yaml
# Verhoog gain in config
sdr:
  devices:
    - gain: 40  # Ipv 'auto', probeer 20-50
```

## 📊 Frequentie Bereik Info

| Band | Frequentie | Gebruik | SDR Coverage (2.4 MHz) |
|------|------------|---------|------------------------|
| Tetra Mobile | 380-385 MHz | Portofoons | 381.3-383.7 MHz @ 382.5 |
| Tetra Base | 390-395 MHz | Basisstations | 391.3-393.7 MHz @ 392.5 |
| FM Radio | 87.5-108 MHz | Calibratie | Full band |
| PMR446 | 446 MHz | Walkie-talkies | 444.8-447.2 MHz @ 446 |

## 📡 Antenne Tips

### Voor 380 MHz (Tetra Mobile)

- **1/4 wave monopole**: 19.6 cm verticaal
- **1/2 wave dipole**: 39.2 cm totaal
- **Ground plane**: Gebruik metalen plaat/dak als ground

### Voor 390 MHz (Tetra Base)

- **1/4 wave monopole**: 19.2 cm verticaal
- **Richting**: Verticaal voor beste ontvangst

### Bouw Zelf

```
Simple 1/4 wave voor 382 MHz:
- Draad: 19.6 cm lang
- Connector: SMA male naar RTL-SDR
- Mount: Verticaal, zo hoog mogelijk
```

## ⚠️ Legal & Privacy

**BELANGRIJK**: 
- Het afluisteren van Tetra communicatie is **illegaal** in Nederland
- Deze detector detecteert alleen de **aanwezigheid** van signalen
- De inhoud wordt **niet** gedecodeerd of opgeslagen
- Gebruik alleen voor legale doeleinden (waarschuwingssystemen)

## 🔮 Roadmap

- [ ] Web dashboard met real-time grafieken
- [ ] Audio alerts bij detectie

## 🤝 Contributing

Pull requests welkom! Voor grote changes, open eerst een issue.

## 📄 License

MIT License - zie LICENSE file

## 🙏 Credits

- RTL-SDR community
- Anthropic Claude voor development assistance
- Tetra standard documentatie

---

**Made with ❤️ for RF enthusiasts**