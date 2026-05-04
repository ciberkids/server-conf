#!/bin/bash
# Send a Telegram alert at boot if any RAID array is degraded or has failed members.
hostname=$(hostname)
issues=()

while IFS= read -r array; do
    md_name=$(basename "$array")
    detail=$(mdadm --detail "$array" 2>/dev/null) || continue
    state=$(echo "$detail" | awk -F': ' '/^\s+State :/{gsub(/^[[:space:]]+/,"",$2); print $2}')
    if echo "$state" | grep -qiE 'degraded|failed'; then
        failed_devs=$(echo "$detail" | awk '/faulty/{print $NF}' | tr '\n' ' ' | sed 's/ $//')
        issues+=("${md_name}: ${state} — failed: ${failed_devs:-unknown}")
    fi
done < <(find /dev/md/ -maxdepth 1 -type b -o -type l 2>/dev/null | sort)

if [ ${#issues[@]} -gt 0 ]; then
    msg="[${hostname}] RAID BOOT ALERT: degraded array detected:"$'\n'
    for issue in "${issues[@]}"; do
        msg+="  • ${issue}"$'\n'
    done
    /usr/bin/telegram-send "$msg"
fi
