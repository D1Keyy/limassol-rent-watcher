#!/usr/bin/env bash
# Install the watcher on an Ubuntu/Debian server as a systemd timer (every 15 min).
# Run as the normal login user (sudo is used where needed):
#   curl -fsSL https://raw.githubusercontent.com/D1Keyy/limassol-rent-watcher/main/deploy/setup_server.sh | bash
# Then put .env (and optionally state/seen.json) into ~/limassol-rent-watcher/.
set -euo pipefail

REPO=https://github.com/D1Keyy/limassol-rent-watcher.git
DIR="$HOME/limassol-rent-watcher"

sudo apt-get update -qq
sudo apt-get install -y -qq git python3-venv tzdata >/dev/null

if [ -d "$DIR/.git" ]; then git -C "$DIR" pull -q; else git clone -q "$REPO" "$DIR"; fi
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
mkdir -p "$DIR/state" "$DIR/logs"

sudo tee /etc/systemd/system/rent-watcher.service >/dev/null <<EOF
[Unit]
Description=Limassol rent watcher: one check
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python -m watcher.main --log-file logs/watch.log
TimeoutStartSec=600
EOF

sudo tee /etc/systemd/system/rent-watcher.timer >/dev/null <<EOF
[Unit]
Description=Run the Limassol rent watcher every 15 minutes

[Timer]
OnCalendar=*:0/15
Persistent=true
RandomizedDelaySec=60

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
echo "Installed in $DIR. After copying .env there, enable with:"
echo "  sudo systemctl enable --now rent-watcher.timer"
