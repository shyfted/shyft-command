package au.com.shyfted.client;

import android.os.SystemClock;
import android.util.Log;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

final class Esp32Client {
    private static final String PING_URL = "http://192.168.0.112/ping";
    private static final int TIMEOUT_MS = 5_000;
    private static final int RETRY_SECONDS = 10;
    private static final int HEALTH_CHECK_SECONDS = 60;

    interface Listener {
        void onPingResult(boolean ok, String response, String error, long latencyMs);
    }

    private final ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor();
    private final Listener listener;
    private boolean started;
    private volatile boolean stopped;

    Esp32Client(Listener listener) {
        this.listener = listener;
    }

    synchronized void ping() {
        if (started || stopped) {
            return;
        }
        started = true;
        executor.execute(this::performPing);
    }

    void stop() {
        stopped = true;
        executor.shutdownNow();
    }

    private void performPing() {
        long startedMs = SystemClock.elapsedRealtime();
        HttpURLConnection connection = null;
        boolean ok = false;
        try {
            connection = (HttpURLConnection) new URL(PING_URL).openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(TIMEOUT_MS);
            connection.setReadTimeout(TIMEOUT_MS);
            connection.setUseCaches(false);

            int code = connection.getResponseCode();
            String response = readBody(code >= 200 && code < 300
                    ? connection.getInputStream()
                    : connection.getErrorStream()).trim();
            ok = code == HttpURLConnection.HTTP_OK && "pong".equals(response);
            long latencyMs = SystemClock.elapsedRealtime() - startedMs;
            String error = ok ? null : "http_code=" + code + " expected=pong";
            Log.i(ShyftedDeviceClient.TAG, "ESP32 ping result"
                    + " url=" + PING_URL
                    + " ok=" + ok
                    + " http_code=" + code
                    + " response=" + response
                    + " latency_ms=" + latencyMs);
            listener.onPingResult(ok, response, error, latencyMs);
        } catch (IOException e) {
            long latencyMs = SystemClock.elapsedRealtime() - startedMs;
            Log.e(ShyftedDeviceClient.TAG, "ESP32 ping failed url=" + PING_URL
                    + " latency_ms=" + latencyMs, e);
            listener.onPingResult(false, null, e.getClass().getSimpleName() + ": " + e.getMessage(), latencyMs);
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
            if (!stopped) {
                executor.schedule(
                        this::performPing,
                        ok ? HEALTH_CHECK_SECONDS : RETRY_SECONDS,
                        TimeUnit.SECONDS
                );
            }
        }
    }

    private static String readBody(InputStream input) throws IOException {
        if (input == null) {
            return "";
        }
        StringBuilder body = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(input, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                body.append(line);
            }
        }
        return body.toString();
    }
}
