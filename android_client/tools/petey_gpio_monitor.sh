#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: petey_gpio_monitor.sh [--range START-END] [--log-file PATH]

Continuously monitors exported GPIO inputs on the connected Petey device and
prints only when a monitored GPIO changes state.

Options:
  --range START-END   Restrict monitoring to GPIO numbers within the inclusive range.
  --log-file PATH     Write all output and the exit summary to PATH.
  -h, --help          Show this help.
EOF
}

range_start=""
range_end=""
log_file=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --range)
      [[ $# -ge 2 ]] || { usage >&2; exit 1; }
      [[ "$2" == *-* ]] || { echo "Invalid range format: $2" >&2; exit 1; }
      range_start="${2%%-*}"
      range_end="${2##*-}"
      [[ "$range_start" =~ ^[0-9]+$ && "$range_end" =~ ^[0-9]+$ && "$range_start" -le "$range_end" ]] || {
        echo "Invalid range values: $2" >&2
        exit 1
      }
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
  log_file="/tmp/petey_gpio_monitor_${timestamp}.log"
fi

: > "$log_file"
echo "Log file: $log_file" >&2

declare -a gpio_list=()
declare -a gpio_direction=()
declare -a gpio_initial=()
declare -a gpio_count=()

cleanup_requested=0
producer_pid=""
fifo_path=""

print_summary() {
  printf '\nSession Summary\n'
  {
    printf '\nSession Summary\n'
    local i
    for i in "${!gpio_list[@]}"; do
      printf 'gpio%s : %s transitions\n' "${gpio_list[$i]}" "${gpio_count[$i]:-0}"
    done
  } >> "$log_file"

  local i
  for i in "${!gpio_list[@]}"; do
    printf 'gpio%s : %s transitions\n' "${gpio_list[$i]}" "${gpio_count[$i]:-0}"
  done
}

find_gpio_index() {
  local needle="$1"
  local i
  for i in "${!gpio_list[@]}"; do
    if [[ "${gpio_list[$i]}" == "$needle" ]]; then
      printf '%s\n' "$i"
      return 0
    fi
  done
  printf '%s\n' "-1"
}

cleanup_runtime() {
  if [[ -n "$producer_pid" ]] && kill -0 "$producer_pid" 2>/dev/null; then
    kill "$producer_pid" 2>/dev/null || true
    wait "$producer_pid" 2>/dev/null || true
  fi

  if [[ -n "$fifo_path" && -p "$fifo_path" ]]; then
    rm -f "$fifo_path"
  fi
}

on_exit() {
  local status=$?

  trap - EXIT

  if [[ $cleanup_requested -eq 0 ]]; then
    cleanup_requested=1
    print_summary
  fi

  cleanup_runtime
  return "$status"
}

trap on_exit EXIT
trap 'exit 130' INT TERM

fifo_path="${TMPDIR:-/tmp}/petey_gpio_monitor.$$.$RANDOM.fifo"
mkfifo "$fifo_path"

adb shell sh -s -- "$range_start" "$range_end" <<'EOF' >"$fifo_path" &
range_start="$1"
range_end="$2"

now() {
  date '+%H:%M:%S.%3N'
}

is_number() {
  case "$1" in
    ''|*[!0-9]*) return 1 ;;
    *) return 0 ;;
  esac
}

in_range() {
  gpio="$1"
  if [ -z "$range_start" ]; then
    return 0
  fi
  [ "$gpio" -ge "$range_start" ] && [ "$gpio" -le "$range_end" ]
}

discover_gpio_entries() {
  for path in /sys/class/gpio/gpio*; do
    [ -d "$path" ] || continue
    gpio="${path##*/gpio}"
    is_number "$gpio" || continue
    in_range "$gpio" || continue
    printf '%s|%s\n' "$gpio" "$path"
  done | sort -n -k1,1
}

get_value() {
  cat "$1" 2>/dev/null | tr -d '\r\n'
}

gpio_entries_file="/data/local/tmp/petey_gpio_entries.$$"
monitored_entries_file="/data/local/tmp/petey_gpio_monitored.$$"
trap 'rm -f "$gpio_entries_file" "$monitored_entries_file"' EXIT

discover_gpio_entries > "$gpio_entries_file"
if [ ! -s "$gpio_entries_file" ]; then
  echo "No exported GPIOs found."
  exit 0
fi

while IFS='|' read -r gpio path; do
  [ -n "$gpio" ] || continue
  direction="$(get_value "$path/direction")"
  initial="$(get_value "$path/value")"
  [ -n "$direction" ] || direction="unknown"
  [ -n "$initial" ] || initial="?"
  printf 'gpio%s  direction=%s  initial=%s\n' "$gpio" "$direction" "$initial"
  case "$direction" in
    in)
      printf '%s|%s\n' "$gpio" "$path" >> "$monitored_entries_file"
      ;;
  esac
done < "$gpio_entries_file"

if [ ! -s "$monitored_entries_file" ]; then
  echo "No input GPIOs to monitor."
  exit 0
fi

while IFS='|' read -r gpio path; do
  [ -n "$gpio" ] || continue
  state_var="state_$gpio"
  count_var="count_$gpio"
  eval "$state_var=\"$(get_value "$path/value")\""
  eval "$count_var=0"
done < "$monitored_entries_file"

while :; do
  while IFS='|' read -r gpio path; do
    [ -n "$gpio" ] || continue
    value="$(get_value "$path/value")"
    state_var="state_$gpio"
    count_var="count_$gpio"
    eval "prev=\${$state_var}"
    if [ -n "$value" ] && [ "$value" != "$prev" ]; then
      ts="$(now)"
      printf '%s  gpio%s  %s -> %s\n' "$ts" "$gpio" "$prev" "$value"
      eval "$state_var=\"\$value\""
      eval "$count_var=\$((\${$count_var} + 1))"
    fi
  done < "$monitored_entries_file"
  sleep 0.05
done
EOF

producer_pid=$!

while IFS= read -r line <"$fifo_path"; do
  printf '%s\n' "$line"
  printf '%s\n' "$line" >> "$log_file"

  if [[ "$line" =~ ^gpio([0-9]+)[[:space:]]+direction=([[:alnum:]_-]+)[[:space:]]+initial=([0-9?]+)$ ]]; then
    gpio="${BASH_REMATCH[1]}"
    idx="$(find_gpio_index "$gpio")"
    if [[ "$idx" -lt 0 ]]; then
      idx="${#gpio_list[@]}"
      gpio_list+=("$gpio")
      gpio_direction+=("${BASH_REMATCH[2]}")
      gpio_initial+=("${BASH_REMATCH[3]}")
      gpio_count+=("0")
    else
      gpio_direction[$idx]="${BASH_REMATCH[2]}"
      gpio_initial[$idx]="${BASH_REMATCH[3]}"
      gpio_count[$idx]="${gpio_count[$idx]:-0}"
    fi
    continue
  fi

  if [[ "$line" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}[[:space:]]+gpio([0-9]+)[[:space:]]+([0-9?]+)[[:space:]]+\-\>[[:space:]]+([0-9?]+)$ ]]; then
    gpio="${BASH_REMATCH[1]}"
    idx="$(find_gpio_index "$gpio")"
    if [[ "$idx" -ge 0 ]]; then
      gpio_count[$idx]=$(( ${gpio_count[$idx]:-0} + 1 ))
    fi
    continue
  fi
done

producer_status=0
set +e
wait "$producer_pid"
producer_status=$?
set -e

if [[ $producer_status -ne 0 ]]; then
  echo "adb monitor exited with status $producer_status" >&2
  exit "$producer_status"
fi
