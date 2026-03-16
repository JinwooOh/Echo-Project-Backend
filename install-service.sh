#!/bin/bash
# Install Music Agent Backend as systemd service (runs 24/7, survives SSH disconnect)
# Run on the Proxmox VM (or any Linux host) where the backend lives.
#
# Usage: sudo ./install-service.sh [user] [install-dir]
# Example: sudo ./install-service.sh
#          sudo ./install-service.sh echo /home/echo/music-agent
#
# After install: backend runs on boot and restarts on crash.

set -e

SERVICE_NAME="music-agent"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_FILE="${SCRIPT_DIR}/${SERVICE_NAME}.service"

USER="${1:-echo}"
INSTALL_DIR="${2:-/home/echo/music-agent}"

echo "Installing Music Agent systemd service..."
echo "  User: $USER"
echo "  Path: $INSTALL_DIR"
echo ""

# Create service with correct paths
TMP=$(mktemp)
sed -e "s|User=.*|User=$USER|" \
    -e "s|Group=.*|Group=$USER|" \
    -e "s|/home/echo/music-agent|$INSTALL_DIR|g" \
    "$SERVICE_FILE" > "$TMP"

sudo cp "$TMP" "/etc/systemd/system/${SERVICE_NAME}.service"
rm -f "$TMP"

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo ""
echo "Done. Backend will start on boot and restart on failure."
echo ""
echo "Commands:"
echo "  sudo systemctl start $SERVICE_NAME    # Start now"
echo "  sudo systemctl stop $SERVICE_NAME     # Stop"
echo "  sudo systemctl status $SERVICE_NAME   # Status"
echo "  journalctl -u $SERVICE_NAME -f        # Logs"
echo ""
