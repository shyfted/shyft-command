# LD2410B Phase 2 Reverse Engineering Report

## Executive Summary

Petey was reachable over ADB at `192.168.0.101:5555` during this phase. The Shyfted client and Geniatech services were left running. No Geniatech services were disabled or uninstalled.

Key finding: there is no evidence that Geniatech currently owns or abstracts the LD2410B radar through `/dev/ttyS3`, `/dev/ttyS4`, Android `sensorservice`, a named Binder service, a broadcast API, or the pulled Geniatech APK/native libraries.

Phase 2 native proof-of-life update: a standalone AArch64 probe using Linux `termios2`/`BOTHER` successfully opened and configured both `/dev/ttyS3` and `/dev/ttyS4` at `256000` baud. Neither port produced any raw bytes or LD2410 frames during the capture windows.

Current best architecture estimate is Option A, with moderate confidence:

```text
LD2410B
    |
UART, likely unused by current software
    |
Shyfted Client future native reader
```

The confidence is not high yet because we have not decoded live LD2410B frames. However, the evidence strongly argues against Option B, where Geniatech reads the UART and exposes presence data.

Recommended integration approach: keep the Shyfted-owned native reader scaffold, but do not integrate LCD wake/sleep until the actual hardware data path is identified. `/dev/ttyS3` and `/dev/ttyS4` are currently negative candidates at `256000`.

## UART Ownership Report

### `/dev/ttyS3`

Owner: no current process owner found.

Purpose: unused at runtime based on current counters. Firmware contains an old/commented GPS hint:

```text
/vendor/ueventd.rc:56:#/dev/ttyS3                0600   gps        gps
```

Driver evidence:

```text
3: uart:16550A mmio:0xFE670000 irq:57 tx:0 rx:0 CTS
```

Open-file evidence:

```text
PID=983 ch.epc.launcher
PID=1546 iatech.epc.core
PID=1592 ech.epc.service
PID=2133 hyfted.epdproof
PID=11136 .shyfted.client
```

No `/dev/ttyS3` file descriptor was listed for those processes.

Conclusion: idle and not owned. Confidence: high.

### `/dev/ttyS4`

Owner: no current process owner found.

Purpose: unknown, but idle based on kernel serial counters.

Driver evidence:

```text
4: uart:16550A mmio:0xFE680000 irq:58 tx:0 rx:0 CTS
```

Open-file evidence: no `/dev/ttyS4` file descriptor was listed for Geniatech launcher/core/service, Shyfted EPD proof app, or the Shyfted client.

Conclusion: idle and not owned. Confidence: high.

### `/dev/ttyS1` Context

Not a primary LD2410 candidate. It has active counters:

```text
1: uart:16550A mmio:0xFE650000 irq:56 tx:79676 rx:1140111 RTS|CTS|DTR
```

It is also configured by firmware as Bluetooth-owned:

```text
/dev/ttyS1                0660   bluetooth  net_bt
```

Conclusion: likely Bluetooth/communications UART, not LD2410B. Confidence: high.

## Geniatech Findings

Pulled packages:

```text
com.geniatech.epc.core
com.geniatech.epc.service
com.geniatech.epc.launcher
```

### `com.geniatech.epc.core`

Purpose: E-Ink/display SDK service.

Manifest service:

```text
com.geniatech.el133sdk.epdService
action: geniatech.intent.action.epdService
```

Relevant classes:

```text
com.geniatech.el133sdk.EpdManager
com.geniatech.el133sdk.epdService
com.geniatech.el133sdk.el133Jni
com.geniatech.el133sdk.el315Jni
com.geniatech.el133sdk.utils.FwUpgrade
```

Native libraries:

```text
libel133UsbJni.so
libel133uf1Jni.so
libel315uf1Jni.so
libnativeEpc101.so
libnativeEpc253.so
libnativeEpc253k.so
libnativeEpc285.so
libnativeEpc312.so
libnativeEpcEC133UJ.so
libnativeMT1330.so
```

Interesting native strings:

```text
/dev/spidev3.0
/dev/i2c-3
/dev/bus/usb
IT8951_USB -d /dev/sg
libusb_open_device_with_vid_pid
native_gtkel133uf_processImage
native_gtkel315uf_processImage
```

No relevant strings found for:

```text
LD2410
ld2410b
radar
mmwave
occupancy
ttyS3
ttyS4
256000
```

### `com.geniatech.epc.service`

Purpose: Send image, Bluetooth/network transport, device utility service.

Manifest service:

```text
com.geniatech.epc.service.server.SendImageService
action: geniatech.intent.action.SendImageService
```

Relevant classes:

```text
com.geniatech.epc.service.manager.SendImageManager
com.geniatech.epc.service.protocol.ImageReceiver
com.geniatech.epc.service.protocol.ProtocolHelper
com.geniatech.epc.service.server.BluetoothServer
com.geniatech.epc.service.server.NetworkServer
com.geniatech.epc.service.server.SendImageService
com.geniatech.epc.service.utils.DeviceInfoUtils
com.geniatech.epc.service.utils.ShellUtils
```

No radar or LD2410-specific API was found. The package references `SensorManager` only generically through Android dependencies; Android `sensorservice` itself exposes only the accelerometer.

### `com.geniatech.epc.launcher`

Purpose: launcher UI.

Relevant classes:

```text
com.geniatech.epc.launcher.MainActivity
com.geniatech.epc.launcher.AppListAdapter
```

No UART, radar, LD2410, or presence integration was found.

## Existing APIs

Discovered Geniatech APIs:

```text
geniatech.intent.action.epdService
com.geniatech.el133sdk.EpdManager
geniatech.intent.action.SendImageService
```

These APIs are display/image related. They do not expose radar or presence data based on manifest, class names, strings, and live Binder/service inspection.

Android service registry:

```text
sensorservice: [android.gui.SensorServer]
serial: [android.hardware.ISerialManager]
```

`sensorservice` showed only:

```text
Accelerometer sensor
```

No Android framework radar/presence sensor is exposed.

## Firmware Search Findings

Targeted firmware search for:

```text
LD2410, ld2410b, radar, mmwave, occupancy, ttyS3, ttyS4, /dev/ttyS3, /dev/ttyS4, 256000
```

Relevant results:

```text
/system/vendor/ueventd.rc:56:#/dev/ttyS3                0600   gps        gps
/vendor/etc/media_profiles_V1_0.xml: bitRate="256000"
```

The `256000` hits are media bitrates, not UART baud configuration. No LD2410/radar/mmWave/presence firmware references were found in accessible text/config paths.

General serial-related result:

```text
/system/vendor/bin/lowmem_manage.sh:101:chmod 666 /dev/ttyS*
```

This explains why `/dev/ttyS3` and `/dev/ttyS4` are world-readable/writable, but it does not identify a consuming service.

## Baud Rate Findings

No evidence was found that Geniatech configured a non-default LD2410B baud rate.

Evidence against a Geniatech-configured baud:

- `/dev/ttyS3` and `/dev/ttyS4` kernel counters remain `tx:0 rx:0`.
- No Geniatech process has either UART open.
- No pulled Geniatech APK/native library references `256000`, `ttyS3`, `ttyS4`, `LD2410`, or radar terms.
- Android shell tools reject `256000`, so the previous Java shell-based probe could not configure the LD2410 default baud correctly.

Native `termios2` result:

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

Final UART counters stayed at zero for both candidates:

```text
3: uart:16550A mmio:0xFE670000 irq:57 tx:0 rx:0 CTS
4: uart:16550A mmio:0xFE680000 irq:58 tx:0 rx:0 CTS
```

Conclusion: `256000` was successfully applied with native code, but no live LD2410B data was observed on `/dev/ttyS3` or `/dev/ttyS4`. The baud-rate assumption is technically testable now; the current blocker is hardware/data-path location, not baud configuration. Confidence: high for these two UARTs being silent during the test.

## Architecture Assessment

Option A is most likely:

```text
LD2410B
    |
UART
    |
Shyfted Client
```

More precisely: the LD2410B appears not to be integrated into the Geniatech application stack at all, so Shyfted likely needs to own the integration.

Option B is unlikely:

```text
LD2410B -> UART -> Geniatech Service -> Shyfted Client
```

Evidence against Option B:

- No UART ownership by Geniatech processes.
- No UART activity on `/dev/ttyS3` or `/dev/ttyS4`.
- No Geniatech radar/presence Binder, broadcast, service, provider, or class/string evidence.

Option C is unproven:

```text
LD2410B -> MCU -> Geniatech -> Android
```

No MCU/radar abstraction was found in Android software. Physical inspection or manufacturer documentation would be needed to rule this out completely.

## Recommended Integration Strategy

Continue developing a native LD2410B driver within the Shyfted client.

Justification:

- There is no discovered higher-level Geniatech presence API.
- Candidate UARTs are idle and unowned, reducing conflict risk.
- `/dev/ttyS3` and `/dev/ttyS4` permissions allow access on this build.
- The existing Shyfted app can isolate this as a background reader and keep Geniatech E-Ink integration unchanged.

Immediate next step:

1. Add native Android serial support using `termios2`/`BOTHER`.
2. Set exact baud `256000`.
3. Retest `/dev/ttyS3` and `/dev/ttyS4`.
4. If no frames appear, investigate physical wiring or a possible MCU path.

## Deliverables

Evidence generated in this phase:

```text
phase2_geniatech/
phase2_geniatech/live_uart_evidence.txt
phase2_geniatech/com.geniatech.epc.core.classes.txt
phase2_geniatech/com.geniatech.epc.service.classes.txt
phase2_geniatech/com.geniatech.epc.launcher.classes.txt
phase2_geniatech/*.radar_serial_strings.txt
phase2_geniatech/native_radar_serial_hits.txt
phase2_geniatech/firmware_specific_hits.txt
```

Final answer to the Phase 2 question:

The Shyfted client should not wait for a Geniatech radar API. Based on current evidence, no such API exists and Geniatech does not appear to own `/dev/ttyS3` or `/dev/ttyS4`. Direct Shyfted-side LD2410B communication is likely necessary.
