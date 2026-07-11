package au.com.shyfted.client;

import android.os.SystemClock;
import android.util.Log;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

final class Gpio18PresenceMonitor {
    private static final File GPIO_BASE = new File("/sys/class/gpio/gpio18");
    private static final File GPIO_DIRECTION = new File(GPIO_BASE, "direction");
    private static final File GPIO_VALUE = new File(GPIO_BASE, "value");
    private static final long SAMPLE_INTERVAL_MS = 50L;

    private final Object lock = new Object();
    private ScheduledExecutorService executor;
    private String lastValue;
    private Long presenceStartedElapsedMs;
    private int transitionCount;
    private boolean running;

    void start() {
        synchronized (lock) {
            if (running) {
                return;
            }

            if (!GPIO_VALUE.isFile()) {
                Log.w(ShyftedDeviceClient.TAG, ts() + " GPIO18 monitor unavailable path=" + GPIO_VALUE.getAbsolutePath());
                return;
            }

            String direction = readTrimmed(GPIO_DIRECTION);
            String initial = readTrimmed(GPIO_VALUE);
            if (initial == null || initial.length() == 0) {
                Log.w(ShyftedDeviceClient.TAG, ts() + " GPIO18 monitor unavailable path=" + GPIO_VALUE.getAbsolutePath());
                return;
            }
            lastValue = normalize(initial);
            long now = SystemClock.elapsedRealtime();
            if ("1".equals(lastValue)) {
                presenceStartedElapsedMs = now;
            }

            Log.i(ShyftedDeviceClient.TAG, ts() + " GPIO18 monitor start"
                    + " path=" + GPIO_BASE.getAbsolutePath()
                    + " direction=" + direction
                    + " initial=" + lastValue
                    + " sample_interval_ms=" + SAMPLE_INTERVAL_MS);

            if (!"in".equals(direction)) {
                Log.w(ShyftedDeviceClient.TAG, ts() + " GPIO18 monitor expected input direction but found direction=" + direction);
            }

            executor = Executors.newSingleThreadScheduledExecutor(r -> {
                Thread thread = new Thread(r, "gpio18-monitor");
                thread.setDaemon(true);
                return thread;
            });
            running = true;
            executor.scheduleAtFixedRate(this::sampleOnce, 0L, SAMPLE_INTERVAL_MS, TimeUnit.MILLISECONDS);
        }
    }

    void stop() {
        synchronized (lock) {
            if (!running) {
                return;
            }
            running = false;
            if (executor != null) {
                executor.shutdownNow();
                executor = null;
            }

            String activeSince = presenceStartedElapsedMs == null
                    ? "none"
                    : String.valueOf(SystemClock.elapsedRealtime() - presenceStartedElapsedMs);
            Log.i(ShyftedDeviceClient.TAG, ts() + " GPIO18 monitor summary"
                    + " transitions=" + transitionCount
                    + " last_value=" + lastValue
                    + " active_duration_ms=" + activeSince);
        }
    }

    private void sampleOnce() {
        synchronized (lock) {
            if (!running) {
                return;
            }

            String current = normalize(readTrimmed(GPIO_VALUE));
            if (current == null || current.length() == 0) {
                return;
            }

            if (lastValue == null || lastValue.length() == 0) {
                lastValue = current;
                if ("1".equals(current)) {
                    presenceStartedElapsedMs = SystemClock.elapsedRealtime();
                }
                return;
            }

            if (current.equals(lastValue)) {
                return;
            }

            long now = SystemClock.elapsedRealtime();
            String previous = lastValue;
            lastValue = current;
            transitionCount++;

            Log.i(ShyftedDeviceClient.TAG, ts() + " GPIO18 transition"
                    + " previous=" + previous
                    + " current=" + current
                    + " transitions=" + transitionCount);

            if ("1".equals(current)) {
                presenceStartedElapsedMs = now;
                Log.i(ShyftedDeviceClient.TAG, ts() + " Presence detected");
                return;
            }

            if ("0".equals(current)) {
                long activeMs = presenceStartedElapsedMs == null ? -1L : now - presenceStartedElapsedMs;
                presenceStartedElapsedMs = null;
                if (activeMs >= 0) {
                    Log.i(ShyftedDeviceClient.TAG, ts() + " Presence cleared active_duration_ms=" + activeMs);
                } else {
                    Log.i(ShyftedDeviceClient.TAG, ts() + " Presence cleared");
                }
            }
        }
    }

    private static String readTrimmed(File file) {
        if (file == null || !file.isFile()) {
            return null;
        }

        try (BufferedReader reader = new BufferedReader(new FileReader(file))) {
            StringBuilder builder = new StringBuilder();
            int ch;
            while ((ch = reader.read()) != -1) {
                if (ch != '\n' && ch != '\r') {
                    builder.append((char) ch);
                }
            }
            return builder.toString().trim();
        } catch (IOException e) {
            Log.w(ShyftedDeviceClient.TAG, "GPIO18 monitor read failure path=" + file.getAbsolutePath(), e);
            return null;
        }
    }

    private static String normalize(String value) {
        return value == null ? null : value.trim();
    }

    private static String ts() {
        return new SimpleDateFormat("HH:mm:ss.SSS", Locale.US).format(new Date());
    }
}
