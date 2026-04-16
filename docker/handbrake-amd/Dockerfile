FROM docker.io/jlesage/handbrake:latest

# Install AMD Mesa VA-API Gallium driver for hardware-accelerated video decoding.
# This enables radeonsi VA-API on AMD GPUs (RX 5000/6000/7000 series).
#
# NOTE: VCN hardware HEVC *encoding* (vce_h265 in HandBrake) requires AMD AMF SDK
# which is a proprietary package not available in Alpine repos. Until an Alpine-
# compatible AMF package exists, encoding stays on CPU (x265 software).
# Hardware decoding via VA-API is active and speeds up the decode phase.
#
# To build and push:
#   podman build -t ciberkids/handbrake-amd:latest .
#   podman push ciberkids/handbrake-amd:latest
#
# On update of jlesage/handbrake base image:
#   podman pull docker.io/jlesage/handbrake:latest
#   podman build --no-cache -t ciberkids/handbrake-amd:latest .
#   podman push ciberkids/handbrake-amd:latest

RUN apk add --no-cache mesa-va-gallium

# Point libva at the radeonsi Mesa Gallium driver.
# Required because libva defaults to looking for an Intel or generic driver.
ENV LIBVA_DRIVER_NAME=radeonsi
ENV LIBVA_DRIVERS_PATH=/usr/lib/dri
