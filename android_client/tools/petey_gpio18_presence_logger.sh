#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: petey_gpio18_presence_logger.sh [options]

Logs GPIO18 transitions from a connected Petey device without changing the
running Shyfted application or Android services.

Options:
  --duration SECONDS       Stop after SECONDS. Default: run until interrupted.
  --poll-ms MS             Poll interval in milliseconds. Default: 20.
  --idle-timeout SECONDS   Emit an idle-timeout candidate after inactive time.
                           Default: 30.
  --active-level 0|1       GPIO value interpreted as presence. Default: 1.
  --log-file PATH          Write a copy of output to PATH.
  -h, --help               Show this help.
EOF
}

duration_seconds=""
poll_ms=20
idle_timeout_seconds=30
active_level=1
log_file=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --duration)
      [[ $# -ge 2 && "$2" =~ ^[0-9]+$ ]] || { usage >&2; exit 1; }
      duration_seconds="$2"
      shift 2
      ;;
    --poll-ms)
      [[ $# -ge 2 && "$2" =~ ^[0-9]+$ && "$2" -gt 0 ]] || { usage >&2; exit 1; }
      poll_ms="$2"
      shift 2
      ;;
    --idle-timeout)
      [[ $# -ge 2 && "$2" =~ ^[0-9]+$ ]] || { usage >&2; exit 1; }
      idle_timeout_seconds="$2"
      shift 2
      ;;
    --active-level)
      [[ $# -ge 2 && "$2" =~ ^[01]$ ]] || { usage >&2; exit 1; }
      active_level="$2"
      shift 2
      ;;
    --log-file)
      [[ $# -ge 2 ]] || { usage >&2; exit 1; }
      log_file="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v adb >/dev/null 2>&1; then
  echo "adb not found on PATH" >&2
  exit 1
fi

timestamp="$(date +%Y%m%d_%H%M%S)"
if [[ -z "$log_file" ]]; then
  log_file="/tmp/petey_gpio18_presence_${timestamp}.log"
fi

: > "$log_file"
echo "Log file: $log_file" >&2

adb shell sh -s -- "$duration_seconds" "$poll_ms" "$idle_timeout_seconds" "$active_level" <<'EOF' | tee -a "$log_file"
duration_seconds="$1"
poll_ms="$2"
idle_timeout_seconds="$3"
active_level="$4"

gpio_path="/sys/class/gpio/gpio18"
value_path="$gpio_path/value"
direction_path="$gpio_path/direction"
start_epoch="$(date +%s)"
poll_sleep="$(printf '%d.%03d' "$((poll_ms / 1000))" "$((poll_ms % 1000))")"
idle_timeout_ms="$((idle_timeout_seconds * 1000))"

now_hms() {
  date '+%H:%M:%S.%3N'
}

now_epoch_ms() {
  date '+%s%3N'
}

level_name() {
  case "$1" in
    1) printf 'HIGH' ;;
    0) printf 'LOW' ;;
    *) printf 'UNKNOWN' ;;
  esac
}

read_gpio() {
  cat "$value_path" 2>/dev/null | tr -d '\r\n'
}

is_presence() {
  [ "$1" = "$active_level" ]
}

if [ ! -r "$value_path" ]; then
  echo "$(now_hms)  GPIO18 unavailable path=$value_path"
  exit 2
fi

direction="$(cat "$direction_path" 2>/dev/null | tr -d '\r\n')"
[ -n "$direction" ] || direction="unknown"

initial="$(read_gpio)"
if [ -z "$initial" ]; then
  echo "$(now_hms)  GPIO18 unreadable path=$value_path"
  exit 2
fi

last="$initial"
last_change_ms="$(now_epoch_ms)"
active_since_ms=""
inactive_since_ms=""
idle_reported=0
transition_count=0
active_total_ms=0
release_count=0

printf '%s  GPIO18 logger start path=%s direction=%s initial=%s active_level=%s poll_ms=%s idle_timeout_s=%s\n' \
  "$(now_hms)" "$gpio_path" "$direction" "$(level_name "$initial")" "$active_level" "$poll_ms" "$idle_timeout_seconds"

if is_presence "$initial"; then
  active_since_ms="$last_change_ms"
  printf '%s  Presence initially active\n' "$(now_hms)"
else
  inactive_since_ms="$last_change_ms"
  printf '%s  Presence initially inactive\n' "$(now_hms)"
fi

while :; do
  if [ -n "$duration_seconds" ]; then
    elapsed_s="$(( $(date +%s) - start_epoch ))"
    [ "$elapsed_s" -lt "$duration_seconds" ] || break
  fi

  current="$(read_gpio)"
  now_ms="$(now_epoch_ms)"

  if [ -n "$current" ] && [ "$current" != "$last" ]; then
    previous="$last"
    previous_change_ms="$last_change_ms"
    last="$current"
    last_change_ms="$now_ms"
    transition_count="$((transition_count + 1))"
    interval_ms="$((now_ms - previous_change_ms))"

    printf '%s  GPIO18 %s  previous=%s interval_ms=%s transitions=%s\n' \
      "$(now_hms)" "$(level_name "$current")" "$(level_name "$previous")" "$interval_ms" "$transition_count"

    if is_presence "$current"; then
      active_since_ms="$now_ms"
      inactive_since_ms=""
      idle_reported=0
      printf '%s  Presence detected\n' "$(now_hms)"
    else
      inactive_since_ms="$now_ms"
      idle_reported=0
      if [ -n "$active_since_ms" ]; then
        active_duration_ms="$((now_ms - active_since_ms))"
        active_total_ms="$((active_total_ms + active_duration_ms))"
        release_count="$((release_count + 1))"
        printf '%s  Presence cleared active_duration_ms=%s\n' "$(now_hms)" "$active_duration_ms"
      else
        printf '%s  Presence cleared\n' "$(now_hms)"
      fi
      active_since_ms=""
    fi
  fi

  if [ -n "$inactive_since_ms" ] && [ "$idle_reported" -eq 0 ]; then
    inactive_ms="$((now_ms - inactive_since_ms))"
    if [ "$inactive_ms" -ge "$idle_timeout_ms" ]; then
      printf '%s  Idle timeout candidate inactive_duration_ms=%s\n' "$(now_hms)" "$inactive_ms"
      idle_reported=1
    fi
  fi

  sleep "$poll_sleep"
done

now_ms="$(now_epoch_ms)"
if [ -n "$active_since_ms" ]; then
  active_total_ms="$((active_total_ms + now_ms - active_since_ms))"
fi

if [ "$release_count" -gt 0 ]; then
  avg_active_ms="$((active_total_ms / release_count))"
else
  avg_active_ms=0
fi

printf '%s  GPIO18 logger summary transitions=%s last=%s active_total_ms=%s releases=%s avg_active_ms=%s\n' \
  "$(now_hms)" "$transition_count" "$(level_name "$last")" "$active_total_ms" "$release_count" "$avg_active_ms"
EOF
