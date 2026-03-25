#!/bin/bash

# DGS-X - 1.0.1 Universal Installer
# Targets: Arch, Debian/Ubuntu, openSUSE, Fedora
# Integration: Systemd User Service & Desktop Entry

set -e

PROJECT_NAME="dgs-x"
REVERSE_ID="com.carlositaro.dgsx"

# PATH LOGIC: Check if running from root or scripts/ directory
SCRIPT_DIR=$(readlink -f "$(dirname "$0")")
if [[ "$(basename "$SCRIPT_DIR")" == "scripts" ]]; then
    PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi

INSTALL_DIR="$HOME/.local/share/$PROJECT_NAME"
SERVICE_NAME="$PROJECT_NAME.service"
RULES_FILE="99-dgs-x.rules"
ICON_DEST_DIR="$HOME/.local/share/icons/hicolor/64x64/apps"
APPS_DIR="$HOME/.local/share/applications"

echo "------------------------------------------"
echo "🚀 Installing DGS-X 1.0.1 Stable Release"
echo "------------------------------------------"

# 1. Distro Detection & Dependency Management
if [ -f /etc/os-release ]; then
    . /etc/os-release
fi

echo "Checking for system dependencies on $NAME..."
case $ID in
    fedora)
        sudo dnf install -y python3-devel gcc
        ;;
    opensuse-tumbleweed|opensuse-leap)
        sudo zypper install -y python3-devel gcc
        ;;
    arch)
        sudo pacman -S --needed --noconfirm python gcc
        ;;
    deb|ubuntu|debian)
        sudo apt-get update
        sudo apt-get install -y python3-dev python3-venv build-essential
        ;;
esac

# 2. Prepare Directory Structure
mkdir -p "$INSTALL_DIR/assets"
mkdir -p "$ICON_DEST_DIR"
mkdir -p "$APPS_DIR"

# 3. Copy Files (Using PROJECT_ROOT to locate src and assets)
if [ -f "$PROJECT_ROOT/src/dgs-x.py" ]; then
    cp "$PROJECT_ROOT/src/dgs-x.py" "$INSTALL_DIR/"
    if [ -d "$PROJECT_ROOT/assets" ]; then
        cp -r "$PROJECT_ROOT/assets/." "$INSTALL_DIR/assets/"
    fi
    chmod +x "$INSTALL_DIR/dgs-x.py"
    echo "✅ Core and Assets copied successfully."
else
    echo "❌ Error: src/dgs-x.py not found at $PROJECT_ROOT/src/"
    exit 1
fi

# 4. Setup Python Virtual Environment
echo "Setting up Python Virtual Environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install evdev

# 5. Register System Icon
if [ -f "$INSTALL_DIR/assets/dgs-x_trayicon.png" ]; then
    cp "$INSTALL_DIR/assets/dgs-x_trayicon.png" "$ICON_DEST_DIR/$REVERSE_ID.png"
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

# 6. Create Desktop Entry
echo "Generating desktop entry..."
cat <<EOF > "$APPS_DIR/$REVERSE_ID.desktop"
[Desktop Entry]
Name=DGS-X
Comment=Gamepad Mouse Emulator
Exec=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/dgs-x.py
Icon=$REVERSE_ID
Terminal=false
Type=Application
Categories=Utility;Settings;
StartupWMClass=$REVERSE_ID
X-GNOME-UsesNotifications=true
EOF
chmod +x "$APPS_DIR/$REVERSE_ID.desktop"

# 7. Install UDEV Rules (Check root and src)
UDEV_SRC=""
[ -f "$PROJECT_ROOT/$RULES_FILE" ] && UDEV_SRC="$PROJECT_ROOT/$RULES_FILE"
[ -f "$PROJECT_ROOT/src/$RULES_FILE" ] && UDEV_SRC="$PROJECT_ROOT/src/$RULES_FILE"

if [ -n "$UDEV_SRC" ]; then
    echo "Applying UDEV rules..."
    sudo cp "$UDEV_SRC" /etc/udev/rules.d/
    sudo udevadm control --reload-rules
    sudo udevadm trigger
fi

# 8. Group Membership
if ! groups $USER | grep &>/dev/null "\binput\b"; then
    echo "Adding user to 'input' group..."
    sudo usermod -aG input $USER
fi

# 9. Create Systemd User Service
mkdir -p "$HOME/.config/systemd/user/"
cat <<EOF > "$HOME/.config/systemd/user/$SERVICE_NAME"
[Unit]
Description=DGS-X Gamepad Mouse Emulator
After=graphical-session.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/dgs-x.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "$SERVICE_NAME"

echo "------------------------------------------"
echo "✅ DGS-X Installation Complete!"
echo "Note: You might need to log out and back in for 'input' group changes."
echo "------------------------------------------"
