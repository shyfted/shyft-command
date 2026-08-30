#!/bin/sh
set -eu

ADB_SERIAL="${ADB_SERIAL:-192.168.0.110:5555}"
SHYFTED_PACKAGE="au.com.shyfted.client"
SHYFTED_HOME="${SHYFTED_PACKAGE}/.MainActivity"
VENDOR_LAUNCHER="com.geniatech.epc.launcher"
PROPERTIES_PATH="/sdcard/Android/data/${SHYFTED_PACKAGE}/files/shyfted-client.properties"

expected_properties='device.name=Petey
device.id=petey
cms.url=https://cms.shyfted.com.au'

actual_properties="$(adb -s "$ADB_SERIAL" shell \
  "grep -E '^(device.name|device.id|cms.url)=' '$PROPERTIES_PATH'" | tr -d '\r')"

if [ "$actual_properties" != "$expected_properties" ]; then
  printf '%s\n' "Refusing HOME provisioning: Petey identity/config does not match." >&2
  printf '%s\n' "$actual_properties" >&2
  exit 1
fi

adb -s "$ADB_SERIAL" shell \
  "pm disable-user --user 0 '$VENDOR_LAUNCHER'"
adb -s "$ADB_SERIAL" shell \
  "cmd package set-home-activity --user 0 '$SHYFTED_HOME'"
adb -s "$ADB_SERIAL" shell \
  "am start -W -a android.intent.action.MAIN -c android.intent.category.HOME"

resolved_home="$(adb -s "$ADB_SERIAL" shell \
  "cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME" | \
  tr -d '\r' | tail -1)"

if [ "$resolved_home" != "$SHYFTED_HOME" ]; then
  printf 'Unexpected HOME resolution: %s\n' "$resolved_home" >&2
  exit 1
fi

printf 'Petey HOME provisioned: %s\n' "$resolved_home"
printf 'Vendor launcher disabled for user 0: %s\n' "$VENDOR_LAUNCHER"
