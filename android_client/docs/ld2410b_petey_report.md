# LD2410B Petey Investigation Report

## Executive Summary

Petey was reached over Wi-Fi ADB at `192.168.0.101:5555` and identified as `product:rk3566_epc model:rk3566_epc device:rk3566_r`, Android 11. The Shyfted debug APK installed successfully, the Shyfted client and Geniatech services remained running, and baseline diagnostics were captured.

The likely LD2410B transport remains UART, but live target frames were not decoded in this pass. Petey exposes `/dev/ttyS1`, `/dev/ttyS3`, and `/dev/ttyS4`; `/dev/ttyS3` maps to kernel node `/serial@fe670000`, and `/dev/ttyS4` maps to `/serial@fe680000`. A native proof-of-life reader using Linux `termios2`/`BOTHER` successfully configured both `/dev/ttyS3` and `/dev/ttyS4` at the LD2410B default baud `256000`, but both ports produced `bytes=0 frames=0`.

The current evidence means the application can perform exact 256000-baud native serial access, but the LD2410B is not currently streaming on `/dev/ttyS3` or `/dev/ttyS4`. Either the sensor is wired elsewhere, not powered/enabled, behind another MCU, configured not to stream, or absent from the Android-accessible UART path.

The recommended production architecture is to keep LD2410 handling isolated from the Geniatech E-Ink Binder integration. Add a small background serial reader owned by the Shyfted client process, publish debounced presence state to `MainActivity`, and use that state only to manage the LCD/WebView wake policy. The E-Ink path should remain permanently visible and unchanged.

## Hardware Findings

Status: partially verified over ADB.

Expected LD2410B interface:

- Transport: UART serial.
- Default baud rate: 256000.
Observed tty nodes:

```text
crw-rw-rw- 1 root      root     5,   0 /dev/tty
crw------- 1 root      root   253,   0 /dev/ttyFIQ0
crw-rw-rw- 1 bluetooth net_bt   4,  65 /dev/ttyS1
crw-rw-rw- 1 root      root     4,  67 /dev/ttyS3
crw-rw-rw- 1 root      root     4,  68 /dev/ttyS4
```

Interpretation:

- `/dev/ttyS1` is likely Bluetooth-related because it is owned by `bluetooth:net_bt` and was observed at `1500000` baud.
- `/dev/ttyS3` and `/dev/ttyS4` are plausible internal UART candidates.
- Opening `/dev/ttyS3` logged kernel node `/serial@fe670000`.
- Opening `/dev/ttyS4` logged kernel node `/serial@fe680000`.
- No USB serial node was observed in the captured tty listing.

Run the inventory script when Petey is connected:

```bash
cd /Users/katmeintjes/Shyfted\ GitHub/shyfted_cms/android_client
chmod +x tools/petey_ld2410_inventory.sh
tools/petey_ld2410_inventory.sh /tmp/petey_ld2410_inventory
```

Useful manual checks:

```bash
adb devices -l
adb shell 'ls -al /dev/tty* /dev/serial* /dev/usb* 2>/dev/null'
adb shell 'dmesg 2>/dev/null | grep -i -E "tty|uart|serial|usb|radar|mmwave|presence|sensor" | tail -300'
adb shell getprop | grep -i -E 'tty|uart|serial|geniatech|rk3566'
```

## Software Findings

Existing Shyfted client structure:

- `MainActivity` owns kiosk/full-screen LCD rendering and currently sets `FLAG_KEEP_SCREEN_ON`.
- `ShyftedDeviceClient` polls the CMS every 5 seconds and sends heartbeats every 60 seconds.
- `PeteyEinkServiceProbe` binds to `com.geniatech.epc.core/com.geniatech.el133sdk.epdService` and sends E-Ink images through the Geniatech Binder API.
- The sensor proof of concept is not started during normal app startup.

Observed production-state packages/processes:

```text
com.geniatech.epc.launcher
com.geniatech.epc.core
com.geniatech.epc.service
com.geniatech.epc.helper
com.geniatech.autotest
com.shyfted.epdproof
au.com.shyfted.client
```

Relevant running processes after install/probe:

```text
system   com.geniatech.epc.launcher
system   com.geniatech.epc.core
system   com.geniatech.epc.service
u0_a102  com.shyfted.epdproof
u0_a101  au.com.shyfted.client
```

Android `sensorservice` exposes only the standard accelerometer. No Android framework presence/radar sensor was exposed.

Android service registry contains `serial: [android.hardware.ISerialManager]`, but no radar/presence-specific Binder service was discovered by name.

Vendor integration still needs deeper APK/native inspection:

```bash
adb shell ps -A | grep -i -E 'geniatech|epc|epd|radar|sensor|presence|human'
adb shell pm list packages -f | grep -i -E 'geniatech|epc|epd|radar|sensor|presence|human'
adb shell service list | grep -i -E 'geniatech|epc|epd|radar|sensor|presence|human'
adb shell logcat -d | grep -i -E 'ld2410|radar|mmwave|presence|human|sensor|tty|uart|serial'
```

No obvious Geniatech radar/presence API was found from package names, running processes, `service list`, `sensorservice`, or log filters. Current evidence suggests Geniatech is not exposing the LD2410B as an Android sensor. This does not yet prove Geniatech is not using the UART internally.

## Communication Findings

Expected serial settings:

- Baud: 256000.
- Mode: raw 8N1.
- Flow control: disabled.
- LD2410 data-frame header: `F4 F3 F2 F1`.
- Length: 16-bit little-endian body length immediately after the header.

Normal target frame fields decoded by the PoC:

| Field | Meaning |
| --- | --- |
| `targetState` | `0` none, `1` moving, `2` stationary, `3` moving and stationary |
| `movingDistanceCm` | moving-target distance |
| `movingEnergy` | moving-target signal energy |
| `stationaryDistanceCm` | stationary-target distance |
| `stationaryEnergy` | stationary-target signal energy |
| `detectionDistanceCm` | detection distance |
| `movingGateEnergy` | optional engineering-mode gate energies |
| `stationaryGateEnergy` | optional engineering-mode gate energies |

The PoC logs raw packets and decoded frames with the `LD2410_FRAME` prefix.

Observed probe results:

```text
/dev/ttyS1: attempted with shell stty, stopped with frames=0.
/dev/ttyS3: attempted with shell stty, kernel opened serial@fe670000, stopped with frames=0.
/dev/ttyS4: attempted with shell stty, kernel opened serial@fe680000, no decoded LD2410 frames observed.
```

Root cause found after the first probe:

```text
stty: unknown speed: 256000
microcom: unknown speed: 256000
```

Supported tested baud rates include `115200`, `230400`, `460800`, `500000`, `921600`, `1000000`, and `1500000`; `250000` and `256000` fail in shell tools. Raw reads at `115200`, `230400`, `460800`, and `500000` on `/dev/ttyS3` and `/dev/ttyS4` produced no bytes.

Native `termios2`/`BOTHER` proof-of-life results:

```text
/dev/ttyS3:
LD2410_NATIVE start port=/dev/ttyS3 baud=256000 duration_seconds=15
LD2410_NATIVE open_success fd=3
LD2410_NATIVE termios2_success
LD2410_NATIVE stop bytes=0 frames=0

/dev/ttyS4:
LD2410_NATIVE start port=/dev/ttyS4 baud=256000 duration_seconds=15
LD2410_NATIVE open_success fd=3
LD2410_NATIVE termios2_success
LD2410_NATIVE stop bytes=0 frames=0
```

Kernel counters after native probing remained unchanged:

```text
3: uart:16550A mmio:0xFE670000 irq:57 tx:0 rx:0 CTS
4: uart:16550A mmio:0xFE680000 irq:58 tx:0 rx:0 CTS
```

Presence behaviour: no raw bytes were received, so there were no decoded no-presence or presence frames and no observable log change when presence was tested. The test proved exact native baud setup, but not live LD2410B communication.

## Proof Of Concept

Source files:

- `app/src/main/java/au/com/shyfted/client/Ld2410Frame.java`
- `app/src/main/java/au/com/shyfted/client/Ld2410StreamDecoder.java`
- `app/src/main/java/au/com/shyfted/client/Ld2410ProbeService.java`
- `app/src/main/java/au/com/shyfted/client/Ld2410SerialCli.java`
- `tools/ld2410_termios2_probe.c`
- `tools/build_ld2410_termios2_probe.sh`

Build:

```bash
cd /Users/katmeintjes/Shyfted\ GitHub/shyfted_cms/android_client
./gradlew :app:assembleDebug
```

Install:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Start a 120-second probe on the default serial port:

```bash
adb shell am startservice \
  -n au.com.shyfted.client/.Ld2410ProbeService \
  --es port /dev/ttyS1 \
  --ei baud 256000 \
  --ei duration_seconds 120
```

Watch output:

```bash
adb logcat | grep -E 'LD2410|ShyftedClient'
```

Try candidate UARTs:

```bash
for port in /dev/ttyS0 /dev/ttyS1 /dev/ttyS2 /dev/ttyS3 /dev/ttyS4 /dev/ttyUSB0 /dev/ttyACM0; do
  adb shell am startservice -n au.com.shyfted.client/.Ld2410ProbeService --es port "$port" --ei baud 256000 --ei duration_seconds 20
  sleep 24
done
```

Important current limitation: this shell-based probe cannot set `256000` on Petey. It is useful for package/service scaffolding and decoder validation only. The native probe can set `256000`, but did not receive bytes on `/dev/ttyS3` or `/dev/ttyS4`.

Native proof-of-life build and run:

```bash
cd /Users/katmeintjes/Shyfted\ GitHub/shyfted_cms/android_client
NDK_DIR=/private/tmp/android-ndk-r26d tools/build_ld2410_termios2_probe.sh /private/tmp/ld2410_termios2_probe
adb push /private/tmp/ld2410_termios2_probe /data/local/tmp/ld2410_termios2_probe
adb shell chmod 755 /data/local/tmp/ld2410_termios2_probe
adb shell "su -c '/data/local/tmp/ld2410_termios2_probe /dev/ttyS3 256000 45'"
adb shell "su -c '/data/local/tmp/ld2410_termios2_probe /dev/ttyS4 256000 45'"
```

Expected demonstration output after native arbitrary-baud support is added:

```text
LD2410_FRAME count=1 raw=F4 F3 F2 F1 ... decoded="Presence=false state=none moving=false stationary=false moving_distance_m=0.00 stationary_distance_m=0.00 detection_distance_m=0.00 moving_energy=0 stationary_energy=0"
LD2410_FRAME count=27 raw=F4 F3 F2 F1 ... decoded="Presence=true state=moving moving=true stationary=false moving_distance_m=1.64 stationary_distance_m=0.00 detection_distance_m=1.64 moving_energy=72 stationary_energy=0"
LD2410_FRAME count=89 raw=F4 F3 F2 F1 ... decoded="Presence=true state=stationary moving=false stationary=true moving_distance_m=0.00 stationary_distance_m=1.58 detection_distance_m=1.58 moving_energy=0 stationary_energy=63"
```

## Integration Recommendations

Recommended production design:

- Add a non-exported `PresenceSensorReader` class, not an exported probe service.
- Implement serial configuration in native code using `termios2`/`BOTHER` so `256000` baud can be set exactly.
- Own one serial reader thread or single-thread executor for the lifetime of `MainActivity` or an application-scoped service.
- Decode frames continuously and publish immutable `PresenceState` updates.
- Debounce transitions: wake LCD immediately on presence, sleep LCD only after 30 seconds with no detected target.
- Keep the E-Ink Binder code unchanged and permanently active.
- Include latest presence state in the heartbeat payload for observability after the CMS schema is ready.

LCD policy:

- On presence: clear any sleep timer, ensure LCD view/WebView is visible, acquire/maintain wake behaviour.
- On absence: start a 30-second timer; if still absent at expiry, hide/pause LCD media and release `FLAG_KEEP_SCREEN_ON` or use the vendor display power API if one is confirmed safe.
- Avoid powering down the entire device because that would affect E-Ink management, CMS polling, remote management, and heartbeats.

Threading model:

- Serial read on one background thread.
- UI changes posted to the main thread.
- Heartbeat payload updates guarded by the existing `deviceSpecLock`.

Battery and CPU impact:

- UART reads are low CPU if blocking reads are used.
- Log raw packets only in debug/probe builds; production should log state transitions and errors only.
- Avoid busy polling.

## Risks

- UART ownership conflict if a Geniatech daemon already reads the LD2410B.
- App-level access to `/dev/tty*` may require root, SELinux policy, file permissions, or a vendor Binder/API.
- `su -c stty && cat` is not sufficient on Petey because `256000` baud is unsupported by shell tools.
- Android display power control may vary by Geniatech build; test LCD blanking without affecting E-Ink refreshes or remote management.
- The exported probe service should be removed or made non-exported before a production release.

## Development Roadmap

1. Add a native serial reader with exact `256000` baud support.
2. Retest `/dev/ttyS3` and `/dev/ttyS4` at `256000`.
3. Capture logs for nobody present, approach, standing still, walking away, and multiple nearby people.
4. Verify whether any Geniatech service already owns or exposes the sensor through deeper APK/native analysis if UART still has no traffic.
5. Replace the exported probe service with an internal reader and `PresenceState` model.
6. Add LCD wake/sleep policy behind a configuration flag.
7. Report presence in heartbeat payload after CMS schema agreement.
