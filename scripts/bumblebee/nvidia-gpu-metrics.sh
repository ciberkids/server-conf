#!/bin/bash
# NVIDIA GPU metrics for node_exporter's textfile collector (Bumblebee, GTX 1080 Ti).
# Run every 15 s by nvidia-gpu-metrics.timer; read by the node-exporter container from
# /tmp/node_exporter (dir created by /etc/tmpfiles.d/node-exporter-tmpdir.conf).
#
# Single GPU: only the first card is exported and metrics carry no gpu label. A second
# card would need a gpu="<index>" label on every metric (and the Grafana queries updated).
#
# Values nvidia-smi cannot report ("[N/A]", "[Not Supported]") are skipped per metric:
# one non-numeric sample would otherwise make node_exporter reject the WHOLE file.
# If nvidia-smi fails entirely, the previous file is KEPT and node_exporter keeps serving
# its values; the Grafana "Metrics Age" tile is the staleness detector.
set -u

OUTPUT=/tmp/node_exporter/nvidia_gpu.prom
FIELDS=utilization.gpu,utilization.memory,temperature.gpu,power.draw,memory.used,memory.total
FIELDS+=,utilization.encoder,utilization.decoder,fan.speed,power.limit
FIELDS+=,clocks.current.sm,clocks.current.memory,clocks.current.video,clocks.max.sm,clocks.max.memory

line=$(nvidia-smi --query-gpu="$FIELDS" --format=csv,noheader,nounits 2>/dev/null | head -n1)
[ -n "$line" ] || exit 0

IFS=',' read -r util mem_util temp power mem_used mem_total \
    enc dec fan power_limit clk_sm clk_mem clk_video clk_sm_max clk_mem_max <<< "$line"

# emit <name> <help> <value> [integer multiplier]
emit() {
    local value="${3// /}"
    [[ $value =~ ^-?[0-9]+(\.[0-9]+)?$ ]] || return 0
    [ -n "${4:-}" ] && value=$((value * $4))
    printf '# HELP %s %s\n# TYPE %s gauge\n%s %s\n' "$1" "$2" "$1" "$1" "$value"
}

MIB=1048576
TMP=$(mktemp)
{
    emit nvidia_gpu_utilization_percent "GPU utilization percentage" "$util"
    emit nvidia_gpu_memory_utilization_percent "GPU memory utilization percentage" "$mem_util"
    emit nvidia_gpu_temperature_celsius "GPU temperature in Celsius" "$temp"
    emit nvidia_gpu_power_watts "GPU power draw in watts" "$power"
    emit nvidia_gpu_memory_used_bytes "GPU memory used in bytes" "$mem_used" $MIB
    emit nvidia_gpu_memory_total_bytes "GPU memory total in bytes" "$mem_total" $MIB
    emit nvidia_gpu_encoder_utilization_percent "Video encoder (NVENC) utilization percentage" "$enc"
    emit nvidia_gpu_decoder_utilization_percent "Video decoder (NVDEC) utilization percentage" "$dec"
    emit nvidia_gpu_fan_speed_percent "Fan speed as percentage of maximum" "$fan"
    emit nvidia_gpu_power_limit_watts "Enforced board power limit in watts" "$power_limit"
    emit nvidia_gpu_clock_sm_mhz "Current SM clock in MHz" "$clk_sm"
    emit nvidia_gpu_clock_memory_mhz "Current memory clock in MHz" "$clk_mem"
    emit nvidia_gpu_clock_video_mhz "Current video (NVENC/NVDEC) clock in MHz" "$clk_video"
    emit nvidia_gpu_clock_sm_max_mhz "Maximum SM clock in MHz" "$clk_sm_max"
    emit nvidia_gpu_clock_memory_max_mhz "Maximum memory clock in MHz" "$clk_mem_max"
} > "$TMP"

[ -s "$TMP" ] && mv "$TMP" "$OUTPUT" && chmod 644 "$OUTPUT" || rm -f "$TMP"
