#!/bin/bash
set -e

SE_DIR="/usr/lib/Shutter Encoder/usr/bin"
JAVA="$SE_DIR/JRE/bin/java"

# --- VNC Setup ---
cat > /root/.vnc/xstartup << 'XEOF'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec openbox-session
XEOF
chmod +x /root/.vnc/xstartup

# Start TigerVNC on localhost only (websockify bridges to noVNC HTTP)
vncserver :1 \
    -geometry "${VNC_GEOMETRY:-1280x800}" \
    -depth 24 \
    -localhost yes \
    -SecurityTypes None

sleep 2

# --- noVNC Setup (HTTP bridge to VNC) ---
websockify --web /usr/share/novnc/ 6080 localhost:5901 &

# --- Launch Shutter Encoder (foreground) ---
echo "Starting Shutter Encoder from: $SE_DIR"
cd "$SE_DIR"
exec "$JAVA" -Xmx4G -Dswing.aatext=true -jar "$SE_DIR/Shutter Encoder.jar" "$@"
