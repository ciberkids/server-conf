#!/bin/bash
# Request a z2m raw network map WITH routing tables, via the mosquitto client
# binaries that ship inside the mqtt5 container. Read-only: ZDO LQI + Rtg
# queries only. Takes several minutes for ~60 devices.
set -u
CFG=/mnt/data/docker_persistent/zigbee2mqtt/data/configuration.yaml

# no PyYAML on this host; the mqtt block is flat so sed is sufficient
MU=$(sed -n '/^mqtt:/,/^[a-z]/{s/^  user:[[:space:]]*//p}' "$CFG" | head -1 | tr -d "'\"")
MW=$(sed -n '/^mqtt:/,/^[a-z]/{s/^  password:[[:space:]]*//p}' "$CFG" | head -1 | tr -d "'\"")

if [ -z "$MU" ]; then
  echo "FATAL: could not read mqtt user from config" >&2
  exit 1
fi
echo "creds parsed: user=${#MU} chars, pass=${#MW} chars"

sudo podman exec mqtt5 sh -c "rm -f /tmp/nm.json /tmp/nm.err"

# subscriber first, so we cannot miss the response
sudo podman exec -d mqtt5 sh -c \
  "mosquitto_sub -h localhost -u '$MU' -P '$MW' \
     -t zigbee2mqtt/bridge/response/networkmap -C 1 -W 900 \
     > /tmp/nm.json 2>/tmp/nm.err"
sleep 3

sudo podman exec mqtt5 \
  mosquitto_pub -h localhost -u "$MU" -P "$MW" \
  -t zigbee2mqtt/bridge/request/networkmap \
  -m '{"type":"raw","routes":true}' \
  && echo "networkmap requested at $(date +%T)" \
  || echo "PUBLISH FAILED"
