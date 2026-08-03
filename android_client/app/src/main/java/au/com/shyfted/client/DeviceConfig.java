package au.com.shyfted.client;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.util.Properties;

final class DeviceConfig {
    static final String DEFAULT_DEVICE_NAME = "ShyftTab";
    static final String DEFAULT_DEVICE_ID = "shyfttab";
    static final String DEFAULT_CMS_URL = "https://cms.shyfted.com.au";

    private static final String PREFS_NAME = "shyfted_device_config";
    private static final String CONFIG_FILE_NAME = "shyfted-client.properties";
    private static final String KEY_DEVICE_NAME = "device.name";
    private static final String KEY_DEVICE_ID = "device.id";
    private static final String KEY_CMS_URL = "cms.url";
    private static final String KEY_PRESENCE_LCD_POWER_ENABLED = "presence.lcd_power.enabled";
    private static final String KEY_PRESENCE_STABLE_LOW_TIMEOUT_MS = "presence.lcd_power.stable_low_timeout_ms";
    private static final long DEFAULT_PRESENCE_STABLE_LOW_TIMEOUT_MS = 30_000L;

    final String deviceName;
    final String deviceId;
    final String cmsUrl;
    final boolean presenceLcdPowerEnabled;
    final long presenceStableLowTimeoutMs;
    final String source;

    private DeviceConfig(
            String deviceName,
            String deviceId,
            String cmsUrl,
            boolean presenceLcdPowerEnabled,
            long presenceStableLowTimeoutMs,
            String source
    ) {
        this.deviceName = deviceName;
        this.deviceId = deviceId;
        this.cmsUrl = trimTrailingSlash(cmsUrl);
        this.presenceLcdPowerEnabled = presenceLcdPowerEnabled;
        this.presenceStableLowTimeoutMs = presenceStableLowTimeoutMs > 0
                ? presenceStableLowTimeoutMs
                : DEFAULT_PRESENCE_STABLE_LOW_TIMEOUT_MS;
        this.source = source;
    }

    static DeviceConfig load(Context context, Intent intent) {
        DeviceConfig config = defaults();
        config = config.withPreferences(context);
        config = config.withPropertiesFile(context);
        config = config.withIntentOverrides(intent);
        return config;
    }

    File externalConfigFile(Context context) {
        File directory = context.getExternalFilesDir(null);
        if (directory == null) {
            directory = context.getFilesDir();
        }
        return new File(directory, CONFIG_FILE_NAME);
    }

    private static DeviceConfig defaults() {
        return new DeviceConfig(
                DEFAULT_DEVICE_NAME,
                DEFAULT_DEVICE_ID,
                DEFAULT_CMS_URL,
                false,
                DEFAULT_PRESENCE_STABLE_LOW_TIMEOUT_MS,
                "defaults"
        );
    }

    private DeviceConfig withPreferences(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        return merge(
                prefs.getString(KEY_DEVICE_NAME, null),
                prefs.getString(KEY_DEVICE_ID, null),
                prefs.getString(KEY_CMS_URL, null),
                prefs.contains(KEY_PRESENCE_LCD_POWER_ENABLED)
                        ? String.valueOf(prefs.getBoolean(KEY_PRESENCE_LCD_POWER_ENABLED, false))
                        : null,
                prefs.contains(KEY_PRESENCE_STABLE_LOW_TIMEOUT_MS)
                        ? String.valueOf(prefs.getLong(KEY_PRESENCE_STABLE_LOW_TIMEOUT_MS, DEFAULT_PRESENCE_STABLE_LOW_TIMEOUT_MS))
                        : null,
                "preferences"
        );
    }

    private DeviceConfig withPropertiesFile(Context context) {
        File file = externalConfigFile(context);
        if (!file.isFile()) {
            return this;
        }

        Properties properties = new Properties();
        try (FileInputStream input = new FileInputStream(file)) {
            properties.load(input);
        } catch (IOException ignored) {
            return this;
        }

        return merge(
                properties.getProperty(KEY_DEVICE_NAME),
                properties.getProperty(KEY_DEVICE_ID),
                properties.getProperty(KEY_CMS_URL),
                properties.getProperty(KEY_PRESENCE_LCD_POWER_ENABLED),
                properties.getProperty(KEY_PRESENCE_STABLE_LOW_TIMEOUT_MS),
                file.getAbsolutePath()
        );
    }

    private DeviceConfig withIntentOverrides(Intent intent) {
        if (intent == null) {
            return this;
        }

        return merge(
                intent.getStringExtra(KEY_DEVICE_NAME),
                intent.getStringExtra(KEY_DEVICE_ID),
                intent.getStringExtra(KEY_CMS_URL),
                intent.hasExtra(KEY_PRESENCE_LCD_POWER_ENABLED)
                        ? String.valueOf(intent.getBooleanExtra(KEY_PRESENCE_LCD_POWER_ENABLED, false))
                        : null,
                intent.hasExtra(KEY_PRESENCE_STABLE_LOW_TIMEOUT_MS)
                        ? String.valueOf(intent.getLongExtra(KEY_PRESENCE_STABLE_LOW_TIMEOUT_MS, DEFAULT_PRESENCE_STABLE_LOW_TIMEOUT_MS))
                        : null,
                "intent"
        );
    }

    private DeviceConfig merge(
            String newDeviceName,
            String newDeviceId,
            String newCmsUrl,
            String newPresenceLcdPowerEnabled,
            String newPresenceStableLowTimeoutMs,
            String newSource
    ) {
        String mergedDeviceName = valueOrDefault(newDeviceName, deviceName);
        String mergedDeviceId = valueOrDefault(newDeviceId, deviceId);
        String mergedCmsUrl = valueOrDefault(newCmsUrl, cmsUrl);
        boolean mergedPresenceLcdPowerEnabled = booleanOrDefault(
                newPresenceLcdPowerEnabled,
                presenceLcdPowerEnabled
        );
        long mergedPresenceStableLowTimeoutMs = longOrDefault(
                newPresenceStableLowTimeoutMs,
                presenceStableLowTimeoutMs
        );
        String mergedSource = source;

        if (!mergedDeviceName.equals(deviceName)
                || !mergedDeviceId.equals(deviceId)
                || !trimTrailingSlash(mergedCmsUrl).equals(cmsUrl)
                || mergedPresenceLcdPowerEnabled != presenceLcdPowerEnabled
                || mergedPresenceStableLowTimeoutMs != presenceStableLowTimeoutMs) {
            mergedSource = newSource;
        }

        return new DeviceConfig(
                mergedDeviceName,
                mergedDeviceId,
                mergedCmsUrl,
                mergedPresenceLcdPowerEnabled,
                mergedPresenceStableLowTimeoutMs,
                mergedSource
        );
    }

    private static String valueOrDefault(String value, String defaultValue) {
        if (value == null) {
            return defaultValue;
        }

        value = value.trim();
        return value.length() == 0 ? defaultValue : value;
    }

    private static String trimTrailingSlash(String value) {
        value = valueOrDefault(value, DEFAULT_CMS_URL);
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    private static boolean booleanOrDefault(String value, boolean defaultValue) {
        if (value == null) {
            return defaultValue;
        }

        value = value.trim();
        if ("true".equalsIgnoreCase(value) || "1".equals(value) || "yes".equalsIgnoreCase(value)) {
            return true;
        }
        if ("false".equalsIgnoreCase(value) || "0".equals(value) || "no".equalsIgnoreCase(value)) {
            return false;
        }
        return defaultValue;
    }

    private static long longOrDefault(String value, long defaultValue) {
        if (value == null) {
            return defaultValue;
        }

        try {
            long parsed = Long.parseLong(value.trim());
            return parsed > 0 ? parsed : defaultValue;
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }
}
