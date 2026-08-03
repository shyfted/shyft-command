# Petey Phase 3 - Genuine LCD Power Reduction Investigation

Date: 2026-07-22
Device: Petey RK3566 EPC board at `192.168.0.106:5555`
Scope: LCD/display power only. E-Ink, CMS, website, firmware, SELinux, and persistent boot behavior were not modified.

## Executive Summary

Phase 3 did not prove genuine LCD power reduction yet.

The current Phase 2 implementation remains a good user-experience solution, but it is not a validated power-saving solution. It sets Android/window brightness to the lowest available level and displays a black overlay. Android still reports the display as `ON`, the display suspend blocker remains held, and this investigation found no built-in current or power telemetry that can quantify total device savings.

The most promising software candidates found are:

1. Android framework brightness control: safe, application-accessible, but minimum brightness is clamped to `0.035433073` and Android remains `ON`.
2. `/sys/class/graphics/fb0/blank`: root-writable and reversible in testing, but the node does not read back state and Android still reports display `ON`; it needs visual confirmation and external power measurement.
3. Rockchip DRM DPMS property on HDMI-A-1: discovered through `modetest`; potentially capable of a real display-output power state change, but not safely testable from the existing unprivileged app and should be validated with a privileged helper/native probe plus a restore watchdog.
4. Hardware switching of the LCD/backlight supply: likely the most deterministic fallback if software paths cannot produce measured power reduction.

No method is production-ready until total device current is measured at the device input or battery rail.

## Evidence Directory

Evidence is stored in `docs/phase3_evidence/`.

Key files:

- `dumpsys_power_baseline.txt`
- `dumpsys_display_baseline.txt`
- `dumpsys_window_baseline.txt`
- `dumpsys_surfaceflinger_baseline.txt`
- `display_sysfs_devnode_inventory.txt`
- `candidate_control_values_baseline.txt`
- `device_tree_display_inventory.txt`
- `vendor_rockchip_named_candidates.txt`
- `targeted_candidate_strings.txt`
- `lshal_display_power_services.txt`
- `modetest_connectors.txt`
- `test_cmd_display_brightness_0_restore_1.txt`
- `test_fb0_blank_4_restore_0.txt`
- `post_test_health_check.txt`
- `post_test_adb_devices.txt`
- `final_display_gpio_app_state.txt`

## Baseline Power Comparison

The Android power-supply sysfs tree exposes voltage, capacity, and charge status, but no usable `current_now` or `power_now` telemetry was found during the investigation.

Observed normal LCD operation samples:

| State | Voltage | Current | Power | Measurement point | Equipment | Result |
| --- | ---: | ---: | ---: | --- | --- | --- |
| Normal LCD operation | 7.700-7.716 V | Not exposed | Not measurable | `/sys/class/power_supply/rk-bat/voltage_now` | Android sysfs only | Voltage-only evidence |
| Minimum brightness | Not measured | Not exposed | Not measurable | Android sysfs only | Android sysfs only | Requires external meter |
| Phase 2 overlay | Not measured | Not exposed | Not measurable | Android sysfs only | Android sysfs only | Requires external meter |
| Android display sleep | Not used as solution | Not measured | Not measured | N/A | N/A | Previously caused Wi-Fi ADB loss until physical wake |
| Backlight-off state | Not discovered | Not measured | Not measured | N/A | N/A | No `/sys/class/backlight` device present |
| LCD panel-off state | Not confirmed | Not measured | Not measured | N/A | N/A | Candidate paths require external meter |
| Display low-power state | Not confirmed | Not measured | Not measured | N/A | N/A | DRM DPMS candidate found |
| Hardware-switched LCD state | Not implemented | Not measured | Not measured | LCD/backlight supply rail | External inline meter/bench supply required | Proposed fallback only |

Required equipment for valid power measurements:

- Inline DC power meter at Petey's main DC input, or
- Bench supply with current logging feeding the device input, or
- Current probe/shunt on the LCD/backlight supply rail if measuring display-only savings.

Do not estimate savings from battery voltage. Battery voltage movement is too coarse and load-dependent for this task.

## Software Investigation

### Android Display State

Baseline Android state:

- `mWakefulness=Awake`
- `Display Power: state=ON`
- `mGlobalDisplayState=ON`
- Built-in display: `1920 x 1080`, type `INTERNAL`, state `ON`
- `mHoldingDisplaySuspendBlocker=true`
- `mScreenBrightness=1.0`
- `mBacklight=null`

The display appears internally represented as a Rockchip HDMI-style output even though Android labels it "Built-in Screen".

### Sysfs and Device Nodes

Candidate controls found:

| Path | Current value | Permissions | Owner | Writable | Notes |
| --- | --- | --- | --- | --- | --- |
| `/sys/class/graphics/fb0/blank` | Read returns empty | `-rw-r--r--` | `root:root` | root only | Standard fb blank interface; tested with `4` then restored to `0` |
| `/sys/class/graphics/fb0/state` | `0` | `-rw-r--r--` | `root:root` | root only | Did not change during fb blank test |
| `/sys/class/graphics/fb0/modes` | `U:1920x1080p-0` | `-rw-r--r--` | `root:root` | root only | Mode control, not primary power candidate |
| `/sys/class/drm/card0-HDMI-A-1/status` | `connected` | `-rw-rw-rw-` | `system:system` | yes | Status only |
| `/sys/class/drm/card0-HDMI-A-1/enabled` | `enabled` | `-r--r--r--` | `root:root` | no | Read-only from sysfs |
| `/sys/class/drm/card0-HDMI-A-1/dpms` | `On` | `-r--r--r--` | `root:root` | no | DRM DPMS exists, but sysfs node is read-only |
| `/sys/class/leds/fled-en/brightness` | `0` | `-rw-rw-rw-` | `root:root` | yes | Already off; likely front/flash LED, not LCD |
| `/sys/class/leds/fled-pwm4/brightness` | `0` | `-rw-rw-rw-` | `root:root` | yes | Already off; max `127`; not a reduction candidate |
| `/sys/class/gpio/gpio18/value` | `0` or `1` | `-rwxrwxrwx` | `root:root` | yes | Presence input remains available |

No `/sys/class/backlight` device was found. That is important: Android's brightness APIs may not map to a kernel backlight driver on this build.

### DRM

`modetest -c` successfully opened the Rockchip DRM device and found connector `HDMI-A-1`.

Relevant properties:

- Connector: `HDMI-A-1`
- Status: `connected`
- DPMS enum: `On=0`, `Standby=1`, `Suspend=2`, `Off=3`
- DPMS current value: `0`
- Brightness property: range `0..100`, current `50`
- Contrast/saturation/hue properties: range `0..100`, current `50`

This is the strongest software hint that a real low-power display-output state may exist below Android's normal brightness stack.

## Vendor Investigation

Rockchip/vendor display components discovered:

- `/vendor/bin/rockchip.drmservice`
- `rockchip.hardware.outputmanager@1.0::IRkOutputManager/default`
- `/vendor/etc/init/init.rockchip.drmservice.rc`
- `/vendor/etc/init/rockchip.hardware.outputmanager@1.0-service.rc`
- `/vendor/etc/init/lights-rockchip.rc`
- `/system/bin/blank_screen`
- `/system/bin/drmserver`
- `/system/bin/modetest`
- Rockchip output manager libraries including `rockchip.hardware.outputmanager@1.0.so`

Runtime service state:

- `vendor.outputmanager-1-0` is running.
- `rockchip.hardware.outputmanager@1.0::IRkOutputManager/default` is registered.
- `rockchip.drmservice` appears installed but stopped.
- `android.hardware.lights-service.rockchip` is running.

The Rockchip output manager strings show display-setting methods such as brightness, contrast, screen scale, connection state, and display mode handling. No obvious shell-accessible vendor command for reliable LCD panel power-off was found.

Geniatech/EPC components were present, but no clear Geniatech LCD power-management API was identified. The observed Geniatech/EPC activity appears unrelated to this LCD power task and E-Ink was intentionally left untouched.

## Tested Mechanisms

### Android Framework Brightness

Command:

```sh
cmd display set-brightness 0
sleep 3
cmd display set-brightness 1
```

Observed result:

- Android accepted the command.
- `mScreenBrightness` changed from `1.0` to `0.035433073`, not `0`.
- `Display Power: state=ON` remained unchanged.
- `mGlobalDisplayState=ON` remained unchanged.
- GPIO18 remained readable.
- ADB remained connected.
- No Shyfted foreground loss was observed.

Assessment:

Safe and app-adjacent, but not a confirmed genuine LCD power-off path. It is effectively the same class of solution as Phase 2, with Android brightness clamped at the configured minimum.

### Framebuffer Blanking

Command:

```sh
echo 4 > /sys/class/graphics/fb0/blank
sleep 5
echo 0 > /sys/class/graphics/fb0/blank
```

Original value:

- `fb0/blank` did not return a readable value.
- `fb0/state` was `0`.

Observed result:

- Command completed.
- Restore command completed.
- ADB remained connected.
- GPIO18 remained readable.
- Shyfted remained focused after restore.
- `Display Power: state=ON` remained unchanged.
- `mWakefulness=Awake` remained unchanged.
- `fb0/state` remained `0`.

Assessment:

This is a plausible privileged candidate, but not confirmed. Because `fb0/blank` does not read back state and no external power measurement was available, this cannot be called successful yet. The next test should pair `fb0/blank=4` with direct visual observation and an inline power meter.

### DRM DPMS

Command used:

```sh
modetest -c
```

No DPMS write was performed in Phase 3 because:

- The sysfs `dpms` node is read-only.
- Writing DPMS via DRM ioctls or `modetest` can affect the active display pipeline.
- A safe production-style test needs a restore watchdog and external measurement.

Assessment:

Best privileged software candidate. It may genuinely power down the display output path while keeping Android and Linux alive, but it needs a controlled native/helper test.

### Android System Sleep

Not tested as a production candidate in Phase 3. Previous probing with Android power-key/display sleep caused Wi-Fi ADB to go offline until physical wake. That violates the development and standby requirements.

Assessment:

Rejected for this product architecture.

## Measured Power Results

No measured total power reduction was achieved.

The device exposed:

- Battery voltage around `7.700-7.716 V`
- Battery capacity `52%`
- Charger/battery status `Discharging`

The device did not expose reliable total current or total power telemetry through sysfs. Therefore:

- Current: not measured.
- Power: not calculated.
- Savings: not estimated.

Valid Phase 4 validation must use an external meter.

## Permissions Required

| Mechanism | Can existing app control it? | Required privilege | Notes |
| --- | --- | --- | --- |
| Phase 2 overlay/window brightness | yes | normal app | Already implemented behind dev flag |
| `cmd display set-brightness` equivalent | partly | app/system API depending method | Still display `ON`; minimum is clamped |
| `/sys/class/graphics/fb0/blank` | no | root/system or privileged helper | Root-writable only |
| DRM DPMS ioctl/property | no | native privileged helper/daemon | Best software candidate for true display-output power control |
| Rockchip output manager HIDL | no, unless app is privileged/system | system/vendor permission | May expose brightness/mode controls; power-off not confirmed |
| Hardware LCD/backlight switch | app via GPIO/controller only after hardware added | external controller or privileged GPIO | Most deterministic if software cannot save power |

## Risks

- `fb0/blank` and DRM DPMS can blank the display below Android's normal awareness, so bad restore handling could leave the screen dark while Android remains running.
- Android framework brightness is safe but may not reduce backlight or panel power enough to matter.
- Android system sleep is not acceptable because it can break Wi-Fi ADB during development and may interrupt the always-on app model.
- Hardware switching requires board-level validation to avoid back-feeding the panel, breaking hotplug expectations, or powering the display controller while the panel rail is absent.

## Best Software Solution

The best non-privileged software solution remains Phase 2:

- GPIO18 polling in app at 50 ms.
- Stable LOW timeout.
- Black overlay.
- Window brightness minimum.
- Immediate restore on HIGH.

This is safe for kiosk behavior and responsiveness, but it is not a verified electrical power solution.

## Best Privileged Solution

The best privileged path to investigate next is DRM DPMS or framebuffer blanking through a small native/root helper with a watchdog restore.

Recommended Phase 4 privileged probe:

1. External power meter connected.
2. Shyfted foregrounded and GPIO18 monitor running.
3. Helper records current DRM state.
4. Helper applies DPMS `Off` to connector `HDMI-A-1`.
5. Helper restores DPMS `On` automatically after a short timeout unless GPIO18 HIGH wakes earlier.
6. Compare measured input current/power against normal, minimum brightness, and Phase 2 overlay.
7. Repeat at least five cycles.

If DPMS is unreliable, repeat with `fb0/blank=4` and restore to `0`.

## Best Hardware Solution

If software does not produce measured power reduction, the best fallback is a dedicated hardware switch for the LCD/backlight power path.

Recommended design direction:

- Identify LCD panel supply and backlight supply separately.
- Prefer switching the backlight supply first if it is electrically isolated from panel logic.
- Use a load switch or MOSFET sized for measured LCD/backlight current.
- Keep RK3566, Android, Wi-Fi, GPIO18, and E-Ink rails always powered.
- Control the switch from a service-owned GPIO or an external microcontroller such as ESP32.
- Include default-on or fail-on behavior so a software crash does not permanently black the appliance.
- Avoid relay unless current/voltage/noise requirements force it; a solid-state switch is preferable.

Hardware must not be modified until the display connector pinout, supply rails, enable pins, PWM line, and back-feed paths are mapped.

## Final Recommendation

Do not treat Phase 2 as the final power-management implementation.

Proceed to Phase 4 as a measured validation pass:

1. Add an external inline power meter at the Petey input.
2. Measure normal LCD operation, Android minimum brightness, Phase 2 overlay, `fb0/blank=4`, and DRM DPMS Off.
3. Build only a temporary privileged helper/probe for DPMS/fb blank testing, with automatic restore.
4. Select production architecture only after measured total device power reduction is demonstrated.

Production should use:

- Existing app-level GPIO18 policy and UI wake behavior.
- A narrow privileged display-power helper only if DRM/fb blanking proves real savings.
- Hardware switching if software cannot measurably reduce total power.
