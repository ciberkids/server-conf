#!/bin/bash
OUTPUT=/tmp/node_exporter/nvidia_gpu.prom
TMP=$(mktemp)
nvidia-smi --query-gpu=utilization.gpu,utilization.memory,temperature.gpu,power.draw,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | while IFS=", " read util mem_util temp power mem_used mem_total; do
  cat > "$TMP" << EOF
# HELP nvidia_gpu_utilization_percent GPU utilization percentage
# TYPE nvidia_gpu_utilization_percent gauge
nvidia_gpu_utilization_percent $util
# HELP nvidia_gpu_memory_utilization_percent GPU memory utilization percentage
# TYPE nvidia_gpu_memory_utilization_percent gauge
nvidia_gpu_memory_utilization_percent $mem_util
# HELP nvidia_gpu_temperature_celsius GPU temperature in Celsius
# TYPE nvidia_gpu_temperature_celsius gauge
nvidia_gpu_temperature_celsius $temp
# HELP nvidia_gpu_power_watts GPU power draw in watts
# TYPE nvidia_gpu_power_watts gauge
nvidia_gpu_power_watts $power
# HELP nvidia_gpu_memory_used_bytes GPU memory used in bytes
# TYPE nvidia_gpu_memory_used_bytes gauge
nvidia_gpu_memory_used_bytes $((mem_used * 1024 * 1024))
# HELP nvidia_gpu_memory_total_bytes GPU memory total in bytes
# TYPE nvidia_gpu_memory_total_bytes gauge
nvidia_gpu_memory_total_bytes $((mem_total * 1024 * 1024))
EOF
done
[ -s "$TMP" ] && mv "$TMP" "$OUTPUT" && chmod 644 "$OUTPUT" || rm -f "$TMP"
