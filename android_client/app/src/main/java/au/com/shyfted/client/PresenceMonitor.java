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
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

final class PresenceMonitor {
    interface Listener {
        void onPresenceActive(long eventElapsedMs);

        void onPresenceInactive(long eventElapsedMs);
    }

    private static final File GPIO_BASE = new File("/sys/class/gpio/gpio18");
    private static final File GPIO_DIRECTION = new File(GPIO_BASE, "direction");
    private static final File GPIO_VALUE = new File(GPIO_BASE, "value");
    private static final long SAMPLE_INTERVAL_MS = 50L;
    private static final String ACTIVE_VALUE = "1";
    private static final String INACTIVE_VALUE = "0";

    private final Object lock = new Object();
    private final long stableLowTimeoutMs;
    private final Listener listener;
    private ScheduledExecutorService executor;
    private ScheduledFuture<?> idleFuture;
    private String rawValue;
    private boolean stablePresenceActive;
    private boolean running;
    private int rawTransitionCount;

    PresenceMonitor(long stableLowTimeoutMs, Listener listener) {
        this.stableLowTimeoutMs = stableLowTimeoutMs > 0 ? stableLowTimeoutMs : 30_000L;
        this.listener = listener;
    }

    void start() {
        synchronized (lock) {
            if (running) {
                return;
            }

            if (!GPIO_VALUE.isFile()) {
                Log.w(ShyftedDeviceClient.TAG, ts() + " PresenceMonitor unavailable path=" + GPIO_VALUE.getAbsolutePath());
                return;
            }

            String initial = normalize(readTrimmed(GPIO_VALUE));
            if (initial == null || initial.length() == 0) {
                Log.w(ShyftedDeviceClient.TAG, ts() + " PresenceMonitor unreadable path=" + GPIO_VALUE.getAbsolutePath());
                return;
            }

            String direction = normalize(readTrimmed(GPIO_DIRECTION));
            rawValue = initial;
            stablePresenceActive = ACTIVE_VALUE.equals(rawValue);
            executor = Executors.newSingleThreadScheduledExecutor(r -> {
                Thread thread = new Thread(r, "presence-monitor");
                thread.setDaemon(true);
                return thread;
            });
            running = true;

            Log.i(ShyftedDeviceClient.TAG, ts() + " PresenceMonitor start"
                    + " path=" + GPIO_BASE.getAbsolutePath()
                    + " direction=" + direction
                    + " initial_raw=" + levelName(rawValue)
                    + " stable_presence=" + stablePresenceActive
                    + " sample_interval_ms=" + SAMPLE_INTERVAL_MS
                    + " stable_low_timeout_ms=" + stableLowTimeoutMs);

            if (!"in".equals(direction)) {
                Log.w(ShyftedDeviceClient.TAG, ts() + " PresenceMonitor expected input direction but found direction=" + direction);
            }

            if (stablePresenceActive && listener != null) {
                listener.onPresenceActive(SystemClock.elapsedRealtime());
            } else if (INACTIVE_VALUE.equals(rawValue)) {
                startIdleTimerLocked(SystemClock.elapsedRealtime(), "initial_low");
            }

            executor.scheduleAtFixedRate(this::sampleOnce, 0L, SAMPLE_INTERVAL_MS, TimeUnit.MILLISECONDS);
        }
    }

    void stop() {
        synchronized (lock) {
            if (!running) {
                return;
            }
            running = false;
            cancelIdleTimerLocked("monitor_stop");
            if (executor != null) {
                executor.shutdownNow();
                executor = null;
            }
            Log.i(ShyftedDeviceClient.TAG, ts() + " PresenceMonitor summary"
                    + " raw_transitions=" + rawTransitionCount
                    + " raw_last=" + levelName(rawValue)
                    + " stable_presence=" + stablePresenceActive);
        }
    }

    private void sampleOnce() {
        synchronized (lock) {
            if (!running) {
                return;
            }

            String current = normalize(readTrimmed(GPIO_VALUE));
            if (current == null || current.length() == 0 || current.equals(rawValue)) {
                return;
            }

            long now = SystemClock.elapsedRealtime();
            String previous = rawValue;
            rawValue = current;
            rawTransitionCount++;
            Log.i(ShyftedDeviceClient.TAG, ts() + " PresenceMonitor raw GPIO18 transition"
                    + " previous=" + levelName(previous)
                    + " current=" + levelName(current)
                    + " transitions=" + rawTransitionCount);

            if (ACTIVE_VALUE.equals(current)) {
                cancelIdleTimerLocked("gpio_high");
                if (!stablePresenceActive) {
                    stablePresenceActive = true;
                    Log.i(ShyftedDeviceClient.TAG, ts() + " PresenceMonitor stable presence active");
                }
                if (listener != null) {
                    listener.onPresenceActive(now);
                }
                return;
            }

            if (INACTIVE_VALUE.equals(current)) {
                startIdleTimerLocked(now, "gpio_low");
            }
        }
    }

    private void startIdleTimerLocked(long lowStartedElapsedMs, String reason) {
        if (idleFuture != null && !idleFuture.isDone()) {
            return;
        }

        Log.i(ShyftedDeviceClient.TAG, ts() + " PresenceMonitor idle timer started"
                + " reason=" + reason
                + " timeout_ms=" + stableLowTimeoutMs);
        idleFuture = executor.schedule(() -> handleIdleTimeout(lowStartedElapsedMs), stableLowTimeoutMs, TimeUnit.MILLISECONDS);
    }

    private void cancelIdleTimerLocked(String reason) {
        if (idleFuture == null) {
            return;
        }

        boolean cancelled = idleFuture.cancel(false);
        idleFuture = null;
        if (cancelled) {
            Log.i(ShyftedDeviceClient.TAG, ts() + " PresenceMonitor idle timer cancelled reason=" + reason);
        }
    }

    private void handleIdleTimeout(long lowStartedElapsedMs) {
        synchronized (lock) {
            if (!running || !INACTIVE_VALUE.equals(rawValue)) {
                return;
            }

            idleFuture = null;
            long now = SystemClock.elapsedRealtime();
            stablePresenceActive = false;
            Log.i(ShyftedDeviceClient.TAG, ts() + " PresenceMonitor idle timeout reached"
                    + " stable_low_ms=" + (now - lowStartedElapsedMs));
            if (listener != null) {
                listener.onPresenceInactive(now);
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
            Log.w(ShyftedDeviceClient.TAG, "PresenceMonitor read failure path=" + file.getAbsolutePath(), e);
            return null;
        }
    }

    private static String normalize(String value) {
        return value == null ? null : value.trim();
    }

    private static String levelName(String value) {
        if (ACTIVE_VALUE.equals(value)) {
            return "HIGH";
        }
        if (INACTIVE_VALUE.equals(value)) {
            return "LOW";
        }
        return String.valueOf(value);
    }

    private static String ts() {
        return new SimpleDateFormat("HH:mm:ss.SSS", Locale.US).format(new Date());
    }
}
