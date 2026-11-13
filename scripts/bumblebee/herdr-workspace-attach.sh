#!/bin/sh
# Run herdr inside the herdr-workspace container (rootless quadlet, user matteo).
# Installed on Bumblebee as ~/.local/bin/herdr, so `ssh -t bumblebee herdr` attaches
# to the containerised herdr server; any arguments pass through (herdr status, ...).
if [ -t 0 ] && [ -t 1 ]; then tty=-it; else tty=-i; fi
exec podman exec $tty \
    -e TERM="${TERM:-xterm-256color}" -e COLORTERM="${COLORTERM:-truecolor}" \
    herdr-workspace herdr "$@"
