#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-/tmp/petey_ld2410_inventory_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$out_dir"

adb devices -l | tee "$out_dir/adb_devices.txt"
adb shell getprop > "$out_dir/getprop.txt"
adb shell ps -A > "$out_dir/ps-A.txt"
adb shell pm list packages -f > "$out_dir/packages.txt"
adb shell service list > "$out_dir/services.txt"
adb shell 'ls -al /dev /dev/tty* /dev/serial* /dev/usb* 2>/dev/null' > "$out_dir/devices.txt" || true
adb shell 'dmesg 2>/dev/null | grep -i -E "tty|uart|serial|usb|ld2410|radar|mmwave|presence|human|sensor" | tail -300' > "$out_dir/dmesg_sensor_tail.txt" || true
adb logcat -d > "$out_dir/logcat.txt"
adb shell 'logcat -d | grep -i -E "ld2410|radar|mmwave|presence|human|sensor|tty|uart|serial|geniatech|epc|epd"' > "$out_dir/logcat_sensor.txt" || true

echo "Wrote LD2410 inventory to $out_dir"
