#!/bin/bash
podman ps --all --format '{{.Names}} {{.State}}' | while read name state; do
  if [ "$state" = "running" ]; then val=1; else val=0; fi
  echo "podman_container_running{name=\"$name\",server=\"bumblebee\"} $val"
done > /tmp/node_exporter/podman_containers.prom
