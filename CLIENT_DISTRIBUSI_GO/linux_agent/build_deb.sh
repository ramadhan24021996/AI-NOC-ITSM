#!/bin/bash
set -e

echo "Creating Debian package structure..."
rm -rf deb_pkg
mkdir -p deb_pkg/DEBIAN
mkdir -p deb_pkg/opt/osi-agent
mkdir -p deb_pkg/etc/osi-agent
mkdir -p deb_pkg/etc/xdg/autostart
mkdir -p deb_pkg/lib/systemd/system

echo "Building Linux Agent..."
GOOS=linux GOARCH=amd64 go build -o deb_pkg/opt/osi-agent/agent .

# Copy UI Tray Agent
cp linux_tray_agent.py deb_pkg/opt/osi-agent/
chmod 755 deb_pkg/opt/osi-agent/linux_tray_agent.py

# Create Autostart Entry for Desktop Users
cat <<EOF > deb_pkg/etc/xdg/autostart/osi-tray.desktop
[Desktop Entry]
Name=OSI AI Tray Agent
Comment=OSI AI Support Chat & Notifications
Exec=/usr/bin/python3 /opt/osi-agent/linux_tray_agent.py
Terminal=false
Type=Application
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
chmod 644 deb_pkg/etc/xdg/autostart/osi-tray.desktop

# 1. DEBIAN/control
cat <<EOF > deb_pkg/DEBIAN/control
Package: osi-agent
Version: 2.0.0
Section: utils
Priority: optional
Architecture: amd64
Maintainer: OSI AI <admin@osi-ai.com>
Description: OSI AI PC Health Agent for Linux
 A background telemetry and diagnostic agent for the OSI AI ecosystem.
EOF

# 2. DEBIAN/postinst (Run after install)
cat <<EOF > deb_pkg/DEBIAN/postinst
#!/bin/bash
exec < /dev/tty
echo "=========================================="
echo "    OSI AI PC Health Agent Setup"
echo "=========================================="
echo ""
echo -n "Please enter the Master Server IP Address (e.g. 10.20.0.163): "
read -r USER_IP

if [ -z "\$USER_IP" ]; then
    USER_IP="127.0.0.1"
    echo "No IP provided. Defaulting to \$USER_IP"
fi

echo "\$USER_IP" > /etc/osi-agent/server_ip.txt
chmod 644 /etc/osi-agent/server_ip.txt
echo "Server IP successfully configured to \$USER_IP!"
echo ""

echo -n "Masukkan Chrome/Edge Extension ID (kosongkan jika belum ada, bisa diisi nanti): "
read -r USER_EXT_ID

if [ -n "\$USER_EXT_ID" ]; then
    echo "\$USER_EXT_ID" > /etc/osi-agent/ext_id.txt
    chmod 644 /etc/osi-agent/ext_id.txt
    echo "Extension ID berhasil disimpan: \$USER_EXT_ID"
    echo "Browser Chrome/Edge akan otomatis instal ekstensi saat agent restart."
else
    echo "Extension ID tidak diisi. Auto-install browser extension dinonaktifkan."
    echo "Untuk mengaktifkan nanti: echo '<ID>' | sudo tee /etc/osi-agent/ext_id.txt && sudo systemctl restart osi-agent"
fi
echo ""

echo "Installing OSI Agent..."
# Set permissions
chmod 755 /opt/osi-agent/agent
chmod 755 /opt/osi-agent/linux_tray_agent.py
chown -R root:root /opt/osi-agent/

# Register and start service
systemctl daemon-reload
systemctl enable osi-agent.service
systemctl start osi-agent.service
echo "OSI Agent Service started successfully!"
EOF
chmod 755 deb_pkg/DEBIAN/postinst

# 3. DEBIAN/prerm (Run before uninstall)
cat <<EOF > deb_pkg/DEBIAN/prerm
#!/bin/bash
echo "Stopping OSI Agent..."
systemctl stop osi-agent.service || true
systemctl disable osi-agent.service || true
EOF
chmod 755 deb_pkg/DEBIAN/prerm

# 4. DEBIAN/postrm (Run after uninstall)
cat <<EOF > deb_pkg/DEBIAN/postrm
#!/bin/bash
if [ "\$1" = "remove" ] || [ "\$1" = "purge" ]; then
    echo "Removing OSI Agent files..."
    systemctl daemon-reload
    rm -rf /opt/osi-agent
    echo "NOTE: Configuration in /etc/osi-agent is kept. To remove entirely: rm -rf /etc/osi-agent"
fi
EOF
chmod 755 deb_pkg/DEBIAN/postrm

# 5. Systemd Service File
cat <<EOF > deb_pkg/lib/systemd/system/osi-agent.service
[Unit]
Description=OSI AI PC Health Agent
After=network.target

[Service]
Type=simple
ExecStart=/opt/osi-agent/agent
Restart=on-failure
RestartSec=10
User=root
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=osi-agent

[Install]
WantedBy=multi-user.target
EOF

# 6. Default Config Files
echo "127.0.0.1" > deb_pkg/etc/osi-agent/server_ip.txt
echo "UWaVSW9Jz-Yl9wumi7SdHV0o9HSVZCWDlHclqWLUBkE=" > deb_pkg/etc/osi-agent/.key
chmod 644 deb_pkg/etc/osi-agent/server_ip.txt
chmod 600 deb_pkg/etc/osi-agent/.key

echo "Building Debian Package..."
dpkg-deb --build deb_pkg osi-agent-linux_2.0.0_amd64.deb

echo "Done! Package is ready: osi-agent-linux_2.0.0_amd64.deb"
