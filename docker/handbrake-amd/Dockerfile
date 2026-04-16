FROM lscr.io/linuxserver/handbrake:latest

# Base image: linuxserver/handbrake on Arch Linux
# Provides: HandBrake GUI via KasmVNC (web browser + local VNC)
#   Web GUI:  port 3000 (HTTPS) / 3001 (HTTP)
#   Volumes:  /config  /data
#
# AMD GPU support:
#   - Hardware DECODING: enabled via mesa radeonsi VA-API (already in base image)
#   - Hardware ENCODING (vce_h265): NOT available without AMD GPU Pro driver stack.
#     AMD AMF requires proprietary kernel components (EncodeQueueService) that are
#     only present with the full amdgpu-pro stack. The open-source amdgpu + mesa
#     combo does not provide these. x265 software encoding is used instead.
#
# Container needs: --device /dev/dri/renderD128
#
# To rebuild after base update:
#   podman build --no-cache -t ciberkids/handbrake-amd:latest .
#   podman push ciberkids/handbrake-amd:latest

ENV LIBVA_DRIVER_NAME=radeonsi
