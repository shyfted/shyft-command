#!/bin/sh
set -eu

ADB_SERIAL="${ADB_SERIAL:-192.168.0.110:5555}"
ESP32_BASE_URL="${ESP32_BASE_URL:-http://192.168.0.112}"
DRM_CONNECTOR_ID=350
DPMS_SETTLE_SECONDS=1
LCD_STABILIZE_SECONDS=2
OFF_HOLD_SECONDS=10
DEVICE_DPMS_FAILSAFE_SECONDS=20

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"
}

set_dpms() {
  value="$1"
  adb -s "$ADB_SERIAL" shell \
    "modetest -M rockchip -w ${DRM_CONNECTOR_ID}:DPMS:${value}"
}

lcd_on() {
  curl --fail --silent --show-error --max-time 5 \
    -X POST "${ESP32_BASE_URL}/lcd/on"
}

restore() {
  log "recovery: requesting ESP32 LCD ON"
  lcd_on || true
  sleep "$LCD_STABILIZE_SECONDS"
  log "recovery: requesting HDMI DPMS ON"
  set_dpms 0 || true
}

trap restore EXIT HUP INT TERM

log "preflight: Petey identity"
adb -s "$ADB_SERIAL" shell \
  "grep -E '^(device.name|device.id|cms.url)=' /sdcard/Android/data/au.com.shyfted.client/files/shyfted-client.properties"

log "preflight: ESP32 status"
curl --fail --silent --show-error --max-time 5 "${ESP32_BASE_URL}/status"
printf '\n'

log "arming device-local DPMS-On failsafe for ${DEVICE_DPMS_FAILSAFE_SECONDS}s"
adb -s "$ADB_SERIAL" shell \
  "nohup sh -c 'sleep ${DEVICE_DPMS_FAILSAFE_SECONDS}; modetest -M rockchip -w ${DRM_CONNECTOR_ID}:DPMS:0' >/data/local/tmp/shyfted_dpms_failsafe.log 2>&1 &"

log "arming host-side ordered recovery for ${OFF_HOLD_SECONDS}s"
(
  sleep "$OFF_HOLD_SECONDS"
  log "watchdog: requesting ESP32 LCD ON"
  lcd_on
  printf '\n'
  sleep "$LCD_STABILIZE_SECONDS"
  log "watchdog: requesting HDMI DPMS ON"
  set_dpms 0
) &
host_watchdog_pid=$!

log "test: requesting HDMI DPMS OFF"
set_dpms 3
sleep "$DPMS_SETTLE_SECONDS"

log "test: requesting ESP32 LCD OFF"
curl --fail --silent --show-error --max-time 5 \
  -X POST "${ESP32_BASE_URL}/lcd/off"
printf '\n'

log "test: ESP32 status while OFF"
curl --fail --silent --show-error --max-time 5 "${ESP32_BASE_URL}/status"
printf '\n'

wait "$host_watchdog_pid"
sleep 1

log "postflight: ESP32 status"
curl --fail --silent --show-error --max-time 5 "${ESP32_BASE_URL}/status"
printf '\n'

log "postflight: DPMS property"
adb -s "$ADB_SERIAL" shell \
  "modetest -M rockchip -c 2>/dev/null | sed -n '/DPMS:/,+3p' | head -4"

trap - EXIT HUP INT TERM
log "combined proof sequence complete"
