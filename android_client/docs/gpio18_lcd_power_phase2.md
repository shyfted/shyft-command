# Petey GPIO18 LCD Power Phase 2

## Scope

This phase adds a reversible proof-of-concept in the Android client only. It
does not change CMS code, website code, UART handling, or E-Ink power policy.

The feature is disabled by default and was enabled for testing with:

```bash
adb shell am start \
  -n au.com.shyfted.client/.MainActivity \
  --ez presence.lcd_power.enabled true \
  --el presence.lcd_power.stable_low_timeout_ms 30000
```

Default launch after testing logged:

```text
Presence LCD power management disabled
```

## Display-Control Inspection

Observed RK3566/Android state before implementation:

- `MainActivity` uses fullscreen kiosk flags and `FLAG_KEEP_SCREEN_ON`.
- Android `screen_off_timeout` is `2147483647`.
- `dumpsys power` reports `Display Power: state=ON`.
- `dumpsys display` reports one internal 1920 x 1080 display and
  `mBacklight=null`.
- `/sys/class/backlight` exists but contains no backlight devices.
- `/dev/gpiochip*` exists but is `root:root 0600`; it is not usable directly
  from the app process.
- GPIO18 sysfs is app-readable on this build.

Rejected mechanism:

- Android system sleep via power key / display sleep. A manual ADB probe made
  Wi-Fi ADB go offline until Petey was physically woken. That path is too
  invasive for this userspace GPIO-wake proof-of-concept.

Selected mechanism:

- App-owned LCD blanking using `WindowManager.LayoutParams.screenBrightness=0`
  plus a full-screen black overlay view.
- On restore, the overlay is hidden and the previous window brightness value is
  restored.
- Android display power remains `ON`; this POC proves app lifecycle, kiosk
  state, and immediate GPIO-driven restore, but it is not yet proven to remove
  all panel/backlight power.

## Implementation

Files:

- `app/src/main/java/au/com/shyfted/client/PresenceMonitor.java`
- `app/src/main/java/au/com/shyfted/client/LcdPowerController.java`
- `app/src/main/java/au/com/shyfted/client/DeviceConfig.java`
- `app/src/main/java/au/com/shyfted/client/MainActivity.java`

Configuration:

- `presence.lcd_power.enabled`: default `false`.
- `presence.lcd_power.stable_low_timeout_ms`: default `30000`.

Behaviour:

- GPIO18 is sampled every 50 ms.
- Raw GPIO state is logged separately from stable presence state.
- GPIO18 HIGH immediately marks presence active, cancels any idle timer, and
  restores the LCD if blanked.
- GPIO18 LOW starts the app-level idle timer.
- A stable LOW period of 30 seconds requests LCD off.
- Repeated off/on commands are suppressed when the requested state is already
  active.

## Test Results

Build:

```bash
./gradlew :app:assembleDebug
```

Deployment:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Five complete 30-second absence / presence-restore cycles passed:

| Cycle | LOW start | LCD off requested | Stable LOW | HIGH detected | LCD restored | Wake latency |
| --- | --- | --- | ---: | --- | --- | ---: |
| 1 | 01:45:31.188 | 01:46:01.205 | 30,010 ms | 01:46:51.788 | 01:46:51.797 | 11 ms |
| 2 | about 01:47:38.99 | 01:48:09.004 | about 30,010 ms | 01:48:49.288 | 01:48:49.297 | 11 ms |
| 3 | 01:49:26.591 | 01:49:56.620 | 30,021 ms | 01:50:21.091 | 01:50:21.113 | 24 ms |
| 4 | 01:50:37.391 | 01:51:07.427 | 30,021 ms | 01:51:42.491 | 01:51:42.518 | 30 ms |
| 5 | 01:52:02.192 | 01:52:32.222 | 30,022 ms | 01:53:01.692 | 01:53:01.709 | 19 ms |

Average measured app restore latency: about 19 ms.

Side effects checked after the fifth cycle:

- Shyfted app remained foreground:
  `au.com.shyfted.client/.MainActivity`.
- App process remained alive.
- ADB remained reachable over Wi-Fi.
- Android stayed awake and interactive:
  `mWakefulness=Awake`, `Display Power: state=ON`.
- Keyguard stayed hidden:
  `showing=false`, `screenState=SCREEN_STATE_ON`,
  `interactiveState=INTERACTIVE_STATE_AWAKE`.
- No crash or launcher exposure was observed.
- E-Ink code path was not modified. The app did perform normal E-Ink startup
  handling after app relaunch, but the presence LCD cycles did not add E-Ink
  power actions.

## Recommendation

This mechanism is safe to keep developing as a reversible application-layer
presence UX proof-of-concept. It preserves kiosk state, ADB reachability, app
lifecycle, and immediate GPIO-driven restore.

It should not yet be treated as final production LCD power management because
Android display power remains `ON`. Before claiming commercial-appliance-grade
LCD power savings, measure panel/backlight current and investigate a privileged
or vendor-supported display blanking path that can power down the LCD/backlight
without suspending Wi-Fi ADB or the GPIO monitor.
