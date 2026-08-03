# Petey GPIO18 Power Management Phase 1

## Scope

This phase is observation and architecture only. It does not change LCD power
logic, E-Ink rendering, existing Shyfted application behaviour, or production
services.

Known hardware assumptions for this phase:

- Sensor: LD2410B.
- LD2410B OUT is wired to Android GPIO18.
- LD2410B TX/RX are intentionally not connected on this hardware revision.
- Presence is exposed as a single digital signal, not UART data.

## Current Software State

The Android client already contains an observation-only GPIO18 monitor:

- File: `app/src/main/java/au/com/shyfted/client/Gpio18PresenceMonitor.java`.
- Startup: `MainActivity` starts the monitor during normal app startup.
- Source: `/sys/class/gpio/gpio18/value`.
- Direction check: `/sys/class/gpio/gpio18/direction`.
- Poll interval: 50 ms.
- Behaviour: logs transitions only; it does not call LCD, power, WebView,
  wake-lock, or E-Ink APIs.
- Current polarity assumption in app logs: `1` means presence active, `0`
  means presence clear.

This is acceptable as a proof-of-concept logger, but it should not be the final
production monitoring mechanism.

## Logging Utility

For extended testing, use the host-side logger:

```bash
cd android_client
tools/petey_gpio18_presence_logger.sh --poll-ms 20 --idle-timeout 30
```

Useful fixed-duration run:

```bash
tools/petey_gpio18_presence_logger.sh \
  --duration 300 \
  --poll-ms 20 \
  --idle-timeout 30 \
  --log-file /tmp/petey_gpio18_presence.log
```

The logger reads GPIO18 over ADB while the production app is running. It does
not export GPIOs, change direction, set edge modes, stop services, or change
application state.

Example output shape:

```text
09:14:02.120  GPIO18 logger start path=/sys/class/gpio/gpio18 direction=in initial=LOW active_level=1 poll_ms=20 idle_timeout_s=30
09:14:18.044  GPIO18 HIGH  previous=LOW interval_ms=15924 transitions=1
09:14:18.048  Presence detected
09:14:57.212  GPIO18 LOW  previous=HIGH interval_ms=39168 transitions=2
09:14:57.216  Presence cleared active_duration_ms=39168
09:15:27.238  Idle timeout candidate inactive_duration_ms=30022
```

## Live Measurement Status

Captured on Petey over Wi-Fi ADB at `192.168.0.106:5555` on
2026-07-22. The Shyfted Android client was running in the foreground and the
Geniatech services remained running.

GPIO18 path:

```text
/sys/class/gpio/gpio18 -> ../../devices/platform/fdd60000.gpio/gpiochip0/gpio/gpio18
direction=in
```

Permissions observed:

```text
-rwxrwxrwx root root /sys/class/gpio/gpio18/value
-rwxrwxrwx root root /sys/class/gpio/gpio18/direction
-rwxrwxrwx root root /sys/class/gpio/gpio18/edge
crw------- root root /dev/gpiochip0
```

This means the current app can read sysfs GPIO18 directly as an ordinary app
process on this build. GPIO character-device access is present but not
available to an ordinary app without a privileged service or permission change.

Five-minute capture command:

```bash
tools/petey_gpio18_presence_logger.sh \
  --duration 300 \
  --poll-ms 20 \
  --idle-timeout 30 \
  --log-file /tmp/petey_gpio18_presence_phase1.log
```

Raw capture is saved in
`docs/gpio18_presence_phase1_capture_20260722.log`.

Capture summary:

- Initial state: HIGH.
- Final logger state: LOW.
- Transitions: 13.
- Active windows released: 7.
- Total active time during capture: 100,532 ms.
- Average released active window: 14,361 ms.
- No sub-500 ms bounce was observed.
- Several short re-detections occurred after the area was expected to be clear.
  These looked like real sensor re-triggers or residual environmental movement,
  not electrical bounce.

Observed transitions:

| Time | Transition | Interval since previous edge | Interpretation |
| --- | --- | ---: | --- |
| 00:58:35.960 | Initial HIGH | - | Presence active at logger start |
| 00:59:13.245 | HIGH -> LOW | 37,289 ms | Presence cleared |
| 00:59:20.965 | LOW -> HIGH | 7,718 ms | Re-detection |
| 00:59:29.305 | HIGH -> LOW | 8,339 ms | Presence cleared |
| 00:59:35.769 | LOW -> HIGH | 6,455 ms | Re-detection |
| 00:59:40.977 | HIGH -> LOW | 5,220 ms | Presence cleared |
| 01:00:11.084 | Idle timeout | 30,107 ms inactive | Idle candidate |
| 01:00:41.524 | LOW -> HIGH | 60,546 ms | Deliberate trigger detected |
| 01:01:09.031 | HIGH -> LOW | 27,504 ms | Deliberate trigger released |
| 01:01:18.131 | LOW -> HIGH | 9,104 ms | Re-detection |
| 01:01:23.312 | HIGH -> LOW | 5,180 ms | Presence cleared |
| 01:01:45.061 | LOW -> HIGH | 21,746 ms | Re-detection |
| 01:01:50.221 | HIGH -> LOW | 5,161 ms | Presence cleared |
| 01:02:20.303 | Idle timeout | 30,085 ms inactive | Idle candidate |
| 01:02:54.475 | LOW -> HIGH | 64,256 ms | Deliberate trigger detected |
| 01:03:06.314 | HIGH -> LOW | 11,839 ms | Deliberate trigger released |

Timing interpretation:

- Detection latency: GPIO18 rose within the logger window when movement was
  requested. Exact human-cue-to-edge latency was not measured because the manual
  cue timestamp was not recorded independently. Practical observed latency was
  responsive enough for LCD wake policy.
- Release / hold latency: observed active windows after deliberate triggers were
  about 27.5 seconds and 11.8 seconds. The initial already-active state released
  after about 37.3 seconds.
- Debounce behaviour: no rapid electrical bounce was seen. All extra transitions
  were separated by seconds.
- Repeatability: active-high behaviour repeated across all controlled and
  incidental detections.
- Idle timeout candidate: 30 seconds of stable LOW is a reasonable first
  software idle candidate, but production dim/off policy should use longer
  configurable timers.

Recommended next characterization run:

1. Start logger with `--poll-ms 20 --idle-timeout 30`.
2. Keep area clear for 60 seconds.
3. Record an external timestamp while entering the detection zone.
4. Stay still for 30 seconds.
5. Make a small movement.
6. Leave detection zone and record an external timestamp.
7. Keep area clear for 90 seconds.
8. Repeat 10 cycles.

## Confirmed GPIO Behaviour

GPIO18 is active-high:

- Idle: GPIO18 LOW (`0`).
- Presence: GPIO18 HIGH (`1`).
- Polarity: active-high.
- Transition behaviour: clean edges at human-presence timescale; no electrical
  bounce observed in the capture.

## Recommended Monitoring Method

For Phase 1 and field characterization, polling sysfs is acceptable because it
is low risk and easy to run beside production. Use a 20-50 ms interval. This is
more than sufficient for human-presence power policy, where useful transitions
are measured in hundreds of milliseconds to seconds.

For production, prefer an event source when feasible:

- Best technical target: Linux GPIO character device with `libgpiod` or
  equivalent native code, using both-edge events on GPIO18.
- Current permission constraint: `/dev/gpiochip*` is `root:root 0600`, so the
  Shyfted app cannot use it directly as a normal Android app on this build.
- Practical production target for this hardware/software image: Java/Kotlin
  polling of `/sys/class/gpio/gpio18/value` at 50 ms, because sysfs GPIO18 is
  readable by the app and the signal changes slowly enough for LCD policy.
- Higher-rigor option: privileged native daemon or vendor permission change,
  publishing debounced presence state to the Shyfted app.

Avoid tying GPIO reads directly to LCD actions. The monitor should publish
presence state; a separate policy layer should decide what to do with the LCD.

## Future Power Management Architecture

Recommended components:

- `PresenceMonitor`: owns GPIO18 access and emits raw edges plus debounced
  `present` / `not present` state.
- `PresenceStateMachine`: applies debounce, hold, and idle timers.
- `DisplayPowerPolicy`: maps stable presence states to LCD actions.
- `LcdPowerController`: the only component allowed to change brightness, dim,
  wake, or turn the LCD off.
- `MainActivity`: observes display state and remains responsible for UI/WebView
  lifecycle.

Suggested future policy:

```text
Presence detected
        |
        v
Wake LCD immediately if sleeping, restore brightness if dimmed

No movement for configurable dim timeout
        |
        v
Dim LCD

Still no movement for configurable off timeout
        |
        v
Turn LCD off

Movement detected again
        |
        v
Restore LCD immediately
```

Initial production defaults should be conservative:

- Debounce: 100-250 ms after GPIO edge.
- Dim timeout: 30-60 seconds after presence clears.
- LCD-off timeout: 2-5 minutes after presence clears.
- Wake latency target: under 250 ms from confirmed GPIO active edge.

## Limitations

- Sysfs polling can miss very short pulses shorter than the polling interval.
  That is unlikely to matter if LD2410B OUT holds state while presence remains
  active, but live confirmation is required.
- Detection latency cannot be measured exactly from logs alone unless the
  operator records movement cue times. The logger can precisely measure GPIO
  edge-to-edge intervals.
- Android userspace scheduling may add tens of milliseconds of jitter to polling
  timestamps. This is acceptable for Phase 1 policy design.
