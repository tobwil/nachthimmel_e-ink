# Nachthimmel Coburg — E-Ink Display

Night sky info display for a **Waveshare 2.13" V4** e-ink screen on a **Raspberry Pi Zero 2W**.

Shows sun/moon times, aurora probability (KP index), and DWD weather warnings — updated every 20 minutes via cron. Includes a local web UI with a sky map and KP chart.

## Features

- Sunrise/sunset & moonrise/moonset times
- Current moon phase
- KP index from NOAA with aurora alert threshold
- DWD weather warnings for the region
- QR code linking to the web UI
- Flask web UI with sky map and historical KP chart

## Hardware

| Component | Model |
|---|---|
| SBC | Raspberry Pi Zero 2W |
| Display | Waveshare 2.13" e-Paper V4 (250×122 px) |

## Setup

```bash
# On the Raspberry Pi:
git clone https://github.com/tobwil/nachthimmel_e-ink.git
cd nachthimmel_e-ink
bash install.sh
```

`install.sh` will:
- Install Python dependencies (`flask`, `requests`, `ephem`, `qrcode`, `pillow`)
- Auto-detect the Pi's IP and patch it into the scripts
- Install and enable the `nachthimmel-webui` systemd service
- Add a cron job to refresh the display every 20 minutes

## Configuration

Edit the constants at the top of [nachthimmel.py](nachthimmel.py):

```python
LAT = "50.2611"          # Latitude
LON = "10.9639"          # Longitude
KP_COBURG_THRESHOLD = 6  # KP level for aurora alert
WEBUI_PORT = 5001
```

## Usage

```bash
# Manually trigger a display refresh:
python3 nachthimmel.py

# Web UI:
http://<pi-ip>:5001

# Logs:
tail -f ~/nachthimmel.log
```

## Dependencies

- [ephem](https://rhodesmill.org/pyephem/) — astronomical calculations
- [Pillow](https://pillow.readthedocs.io/) — image rendering
- [Flask](https://flask.palletsprojects.com/) — web UI
- [qrcode](https://github.com/lincolnloop/python-qrcode) — QR code generation
- [Waveshare e-Paper library](https://github.com/waveshare/e-Paper) — display driver (install separately into `../lib`)

## License

MIT
