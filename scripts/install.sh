#!/bin/bash

# DGS-X - 1.3.0 Universal Installer
# Targets: Arch, Debian/Ubuntu, openSUSE, Fedora

set -e

PROJECT_NAME="dgs-x"
REVERSE_ID="com.carlositaro.dgsx"

SCRIPT_DIR=$(readlink -f "$(dirname "$0")")
if [[ "$(basename "$SCRIPT_DIR")" == "scripts" ]]; then
    PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi

INSTALL_DIR="$HOME/.local/share/$PROJECT_NAME"
CONFIG_DIR="$HOME/.config/$PROJECT_NAME"
SERVICE_NAME="$PROJECT_NAME.service"
RULES_FILE="99-dgs-x.rules"
ICON_DEST_DIR="$HOME/.local/share/icons/hicolor/64x64/apps"
APPS_DIR="$HOME/.local/share/applications"

echo "------------------------------------------"
echo "🚀 Installing DGS-X 1.3 - STABLE RELEASE"
echo "------------------------------------------"

# 1. Distro Detection & Dependency Management
if [ -f /etc/os-release ]; then
    . /etc/os-release
fi

echo "Checking for system dependencies on ${NAME:-Linux}..."
OS_CHECK="${ID}_${ID_LIKE}"

case $OS_CHECK in
    *fedora*)
        sudo dnf install -y python3-devel gcc python3-tkinter
        ;;
    *opensuse*)
        sudo zypper install -y python3-devel gcc python3-tk
        ;;
    *arch*)
        sudo pacman -S --needed --noconfirm python gcc tk
        ;;
    *debian*|*ubuntu*)
        sudo apt-get update
        sudo apt-get install -y python3-dev python3-venv python3-tk build-essential
        ;;
    *)
        echo "⚠️ Unknown distribution. Ensure python3, tkinter, and gcc are installed."
        ;;
esac

# 2. Prepare Directory Structure
mkdir -p "$INSTALL_DIR/assets"
mkdir -p "$CONFIG_DIR"
mkdir -p "$ICON_DEST_DIR"
mkdir -p "$APPS_DIR"

# 3. Copy Executables & Assets
if [ -f "$PROJECT_ROOT/dgs-x.py" ]; then
    cp "$PROJECT_ROOT/dgs-x.py" "$INSTALL_DIR/"
elif [ -f "$PROJECT_ROOT/src/dgs-x.py" ]; then
    cp "$PROJECT_ROOT/src/dgs-x.py" "$INSTALL_DIR/"
else
    echo "❌ Error: dgs-x.py not found."
    exit 1
fi

if [ -d "$PROJECT_ROOT/assets" ]; then
    cp -r "$PROJECT_ROOT/assets/." "$INSTALL_DIR/assets/"
fi
chmod +x "$INSTALL_DIR/dgs-x.py"

# 4. Setup Virtual Environment
echo "Setting up Virtual Environment and Python dependencies..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install evdev pillow pystray

# 5. Register System Icon
if [ -f "$INSTALL_DIR/assets/dgs-x_trayicon.png" ]; then
    cp "$INSTALL_DIR/assets/dgs-x_trayicon.png" "$ICON_DEST_DIR/$REVERSE_ID.png"
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

# 6. Create Desktop Entry
echo "Generating desktop entry..."
cat <<EOF > "$APPS_DIR/$REVERSE_ID.desktop"
[Desktop Entry]
Name=DGS-X Control Panel
Comment=Gamepad Mouse Emulator & Settings
Exec=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/dgs-x.py
Icon=$REVERSE_ID
Terminal=false
Type=Application
Categories=Utility;Settings;
StartupWMClass=dgs-x
EOF
chmod +x "$APPS_DIR/$REVERSE_ID.desktop"

# 7. UDEV Rules
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
if ! id -nG "$USER" | grep -qw "input"; then
    echo "Adding user to 'input' group..."
    sudo usermod -aG input "$USER"
fi

# 9. Create Systemd User Service
mkdir -p "$HOME/.config/systemd/user/"
cat <<EOF > "$HOME/.config/systemd/user/$SERVICE_NAME"
[Unit]
Description=DGS-X Gamepad Mouse Emulator
After=graphical-session.target udev.target

[Service]
Type=simple
Environment=DISPLAY=:0
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/dgs-x.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "$SERVICE_NAME"

echo "------------------------------------------"
echo "✅ DGS-X 1.3 Installation Complete!"
echo "Control Panel available in your applications menu."
echo "Note: Log out and back in if 'input' group permissions were newly assigned."
echo "------------------------------------------"
