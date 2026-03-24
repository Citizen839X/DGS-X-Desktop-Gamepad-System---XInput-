#!/bin/bash

# DGS-X Uninstaller
# Cleans up all files, services, and icons

set -e

PROJECT_NAME="dgs-x"
REVERSE_ID="com.carlositaro.dgsx"
INSTALL_DIR="$HOME/.local/share/$PROJECT_NAME"
SERVICE_NAME="$PROJECT_NAME.service"
APPS_DIR="$HOME/.local/share/applications"
ICON_PATH="$HOME/.local/share/icons/hicolor/64x64/apps/$REVERSE_ID.png"

echo "------------------------------------------"
echo "🗑️ Uninstalling DGS-X..."
echo "------------------------------------------"

# 1. Stop and Disable Systemd Service
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    echo "Stopping service..."
    systemctl --user stop "$SERVICE_NAME"
fi

if systemctl --user is-enabled --quiet "$SERVICE_NAME"; then
    echo "Disabling service..."
    systemctl --user disable "$SERVICE_NAME"
fi

# 2. Remove Files
echo "Removing application files..."
rm -rf "$INSTALL_DIR"
rm -f "$APPS_DIR/$REVERSE_ID.desktop"
rm -f "$HOME/.config/systemd/user/$SERVICE_NAME"
rm -f "$ICON_PATH"

# 3. Reload Daemons
systemctl --user daemon-reload
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# 4. UDEV Rules (Optional: usually safe to keep, but can be removed)
if [ -f /etc/udev/rules.d/99-dgs-x.rules ]; then
    echo "Removing UDEV rules..."
    sudo rm /etc/udev/rules.d/99-dgs-x.rules
    sudo udevadm control --reload-rules
fi

echo "------------------------------------------"
echo "✅ DGS-X has been successfully removed."
echo "------------------------------------------"
