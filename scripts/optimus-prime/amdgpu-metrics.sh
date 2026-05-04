#!/bin/bash
OUTPUT=/tmp/node_exporter/amdgpu.prom
TMP=$(mktemp)
VRAM_USED=$(cat /sys/class/drm/card0/device/mem_info_vram_used 2>/dev/null)
VRAM_TOTAL=$(cat /sys/class/drm/card0/device/mem_info_vram_total 2>/dev/null)
GPU_BUSY=$(cat /sys/class/drm/card0/device/gpu_busy_percent 2>/dev/null)
cat > "$TMP" << EOF
# HELP amdgpu_memory_used_bytes AMD GPU VRAM used in bytes
# TYPE amdgpu_memory_used_bytes gauge
amdgpu_memory_used_bytes ${VRAM_USED:-0}
# HELP amdgpu_memory_total_bytes AMD GPU VRAM total in bytes
# TYPE amdgpu_memory_total_bytes gauge
amdgpu_memory_total_bytes ${VRAM_TOTAL:-0}
# HELP amdgpu_utilization_percent AMD GPU busy percentage
# TYPE amdgpu_utilization_percent gauge
amdgpu_utilization_percent ${GPU_BUSY:-0}
EOF
install -m 0644 "$TMP" "$OUTPUT"
rm -f "$TMP"
