FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:1 \
    TZ=Europe/Rome \
    PUID=1000 \
    PGID=1000 \
    LIBVA_DRIVER_NAME=radeonsi \
    VNC_GEOMETRY=1280x800

# Install system packages: VNC stack, VA-API drivers, system ffmpeg, utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    # TigerVNC = Xvfb + VNC server in one binary
    tigervnc-standalone-server \
    # Minimal window manager for the Java Swing GUI
    openbox \
    x11-utils xauth dbus-x11 \
    # noVNC for HTTP-based VNC access
    novnc websockify \
    # VA-API hardware acceleration (AMD radeonsi)
    libva2 libva-drm2 mesa-va-drivers vainfo \
    # System ffmpeg with VA-API support (replaces bundled static ffmpeg)
    ffmpeg \
    # sudo is needed by Shutter Encoder's .deb postinst script
    sudo \
    # Utilities
    wget curl ca-certificates procps \
    && rm -rf /var/lib/apt/lists/*

# Download and install Shutter Encoder .deb (bundles JRE 25 + ffmpeg + app)
RUN wget -q -O /tmp/shutter-encoder.deb \
    "https://www.shutterencoder.com/sdc_download/496/?key=drnf0zl1om6sfwndoa1rdoc942mvp5" \
    && dpkg -i /tmp/shutter-encoder.deb \
    && rm /tmp/shutter-encoder.deb

# Replace bundled static ffmpeg/ffprobe with system versions (VA-API enabled)
RUN ln -sf /usr/bin/ffmpeg "/usr/lib/Shutter Encoder/usr/bin/Library/ffmpeg" \
    && ln -sf /usr/bin/ffprobe "/usr/lib/Shutter Encoder/usr/bin/Library/ffprobe"

# Create working directories
RUN mkdir -p /input /output /config /root/.vnc

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5901 6080

VOLUME ["/input", "/output", "/config"]

ENTRYPOINT ["/entrypoint.sh"]
