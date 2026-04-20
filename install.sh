#!/bin/bash
set -e
echo "=== Nachthimmel Coburg Setup ==="

pip3 install flask requests ephem qrcode pillow --break-system-packages

# PI_IP automatisch ermitteln und eintragen
PI_IP=$(hostname -I | awk '{print $1}')
echo "Pi-IP erkannt: $PI_IP"
sed -i "s/192.168.1.100/$PI_IP/" "$(dirname "$0")/nachthimmel.py"
sed -i "s/192.168.1.100/$PI_IP/" "$(dirname "$0")/webui.py"
echo "IP in Skripten eingetragen."

# Systemd Service
sudo cp "$(dirname "$0")/nachthimmel-webui.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nachthimmel-webui
sudo systemctl start nachthimmel-webui

# Cron alle 20 Min
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CRON="*/20 * * * * /usr/bin/python3 ${SCRIPT_DIR}/nachthimmel.py >> /home/zero/nachthimmel.log 2>&1"
( crontab -l 2>/dev/null | grep -v nachthimmel.py; echo "$CRON" ) | crontab -

echo ""
echo "Fertig!"
echo "  Display-Script:  python3 nachthimmel.py"
echo "  Web-UI:          http://$PI_IP:5001"
echo "  Logs:            tail -f ~/nachthimmel.log"
