# Petey headless HOME provisioning

Petey uses Android's normal HOME mechanism for unattended startup and process
recovery. `au.com.shyfted.client/.MainActivity` declares the `HOME` and
`DEFAULT` categories in the application manifest.

The Geniatech system launcher is also a HOME candidate. On Petey's Android 11
image, leaving that launcher enabled allowed its existing HOME task to become
foreground when the Shyfted process was killed, even though PackageManager's
preferred HOME remained Shyfted. Shyfted's process and network work restarted,
but its UI was not returned to the foreground.

Production provisioning therefore:

1. Verifies the persistent Petey identity and CMS URL.
2. Disables `com.geniatech.epc.launcher` for user 0 only.
3. Sets `au.com.shyfted.client` as the persistent default HOME.
4. Launches the generic HOME intent so Shyfted owns a HOME task.

`DeviceConfig` also mirrors any successfully loaded properties/intent
configuration into internal `SharedPreferences`. This avoids a boot-time race
where HOME can launch before app-specific external storage is mounted. The
external properties file remains authoritative whenever it is available; the
internal copy supplies the same Petey identity during early boot.

The ESP32 health check retries after 10 seconds when an early-boot request
fails before Wi-Fi is ready, then repeats every 60 seconds after success. CMS
heartbeat and configuration polling already have their own periodic schedules.

Run once from the repository root while Petey is available over ADB:

```sh
android_client/tools/provision_petey_home.sh
```

ADB is only the provisioning transport. It is not used by Petey at boot or at
runtime. Android stores the package enabled state and preferred HOME selection.

Emergency rollback:

```sh
adb -s 192.168.0.110:5555 shell pm enable com.geniatech.epc.launcher
adb -s 192.168.0.110:5555 shell cmd package set-home-activity --user 0 com.geniatech.epc.launcher
```
