#!/bin/bash
set -e

SE_DIR="/usr/lib/Shutter Encoder/usr/bin"
JAVA="$SE_DIR/JRE/bin/java"

# --- D-Bus session (needed by Java Desktop API) ---
eval "$(dbus-launch --sh-syntax)" 2>/dev/null || true
export DBUS_SESSION_BUS_ADDRESS

# --- VNC Setup ---
cat > /root/.vnc/xstartup << 'XEOF'
#!/bin/sh
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

# --- Launch Shutter Encoder with auto-restart ---
cd "$SE_DIR"
echo "Starting Shutter Encoder from: $SE_DIR"

# Restart loop: if the user closes the window, relaunch after 2s
while true; do
    "$JAVA" -Xmx4G -Dswing.aatext=true -Dsun.desktop=gnome \
        -jar "$SE_DIR/Shutter Encoder.jar" "$@" || true
    echo "[entrypoint] Shutter Encoder exited, restarting in 2s..."
    sleep 2
done
