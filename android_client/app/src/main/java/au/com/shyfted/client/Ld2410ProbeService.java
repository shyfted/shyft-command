package au.com.shyfted.client;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;

import java.io.Closeable;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

public final class Ld2410ProbeService extends Service {
    static final String EXTRA_PORT = "port";
    static final String EXTRA_BAUD = "baud";
    static final String EXTRA_DURATION_SECONDS = "duration_seconds";

    private static final String DEFAULT_PORT = "/dev/ttyS1";
    private static final int DEFAULT_BAUD = 256000;
    private static final int DEFAULT_DURATION_SECONDS = 120;
    private static final long LOG_REPEAT_MS = 1000;

    private ExecutorService executor;
    private ReaderSession readerSession;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        stopProbe();
        String port = stringExtra(intent, EXTRA_PORT, DEFAULT_PORT);
        int baud = intExtra(intent, EXTRA_BAUD, DEFAULT_BAUD);
        int durationSeconds = intExtra(intent, EXTRA_DURATION_SECONDS, DEFAULT_DURATION_SECONDS);

        executor = Executors.newSingleThreadExecutor();
        executor.execute(() -> runProbe(port, baud, durationSeconds));
        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        stopProbe();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void runProbe(String port, int baud, int durationSeconds) {
        long deadlineMs = System.currentTimeMillis() + TimeUnit.SECONDS.toMillis(durationSeconds);
        Ld2410StreamDecoder decoder = new Ld2410StreamDecoder();
        ProbeListener listener = new ProbeListener();

        Log.i(ShyftedDeviceClient.TAG, "LD2410_PROBE start port=" + port
                + " baud=" + baud
                + " duration_seconds=" + durationSeconds);

        try {
            readerSession = startReaderSession(port, baud);
            try (InputStream inputStream = readerSession.inputStream()) {
                byte[] readBuffer = new byte[256];
                while (System.currentTimeMillis() < deadlineMs && !Thread.currentThread().isInterrupted()) {
                    int count = inputStream.read(readBuffer);
                    if (count < 0) {
                        break;
                    }
                    if (count > 0) {
                        decoder.accept(readBuffer, count, listener);
                    }
                }
            }
        } catch (IOException e) {
            Log.e(ShyftedDeviceClient.TAG, "LD2410_PROBE read failure port=" + port
                    + " baud=" + baud
                    + " hint=verify device node, permissions, and su availability", e);
        } finally {
            stopReaderProcess();
            Log.i(ShyftedDeviceClient.TAG, "LD2410_PROBE stop frames=" + listener.frameCount
                    + " non_data_packets=" + listener.nonDataPacketCount);
            stopSelf();
        }
    }

    private ReaderSession startReaderSession(String port, int baud) throws IOException {
        try {
            return FrameworkSerialReaderSession.open(this, port, baud);
        } catch (ReflectiveOperationException | RuntimeException e) {
            Log.w(ShyftedDeviceClient.TAG, "LD2410_PROBE Android SerialManager reader unavailable; trying shell reader"
                    + " port=" + port + " baud=" + baud, e);
        }

        String command = "stty -F " + shellQuote(port) + " " + baud
                + " raw -echo -ixon -ixoff -icanon min 1 time 1"
                + " && cat " + shellQuote(port);
        try {
            Process process = new ProcessBuilder("su", "-c", command).redirectErrorStream(true).start();
            return new ProcessReaderSession(process);
        } catch (IOException suError) {
            Log.w(ShyftedDeviceClient.TAG, "LD2410_PROBE su reader unavailable; trying app-shell reader", suError);
            Process process = new ProcessBuilder("sh", "-c", command).redirectErrorStream(true).start();
            return new ProcessReaderSession(process);
        }
    }

    private synchronized void stopProbe() {
        stopReaderProcess();
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
    }

    private synchronized void stopReaderProcess() {
        if (readerSession != null) {
            try {
                readerSession.close();
            } catch (IOException e) {
                Log.w(ShyftedDeviceClient.TAG, "LD2410_PROBE reader close failure", e);
            } finally {
                readerSession = null;
            }
        }
    }

    private static String shellQuote(String value) {
        return "'" + value.replace("'", "'\\''") + "'";
    }

    private static String stringExtra(Intent intent, String key, String defaultValue) {
        if (intent == null) {
            return defaultValue;
        }
        String value = intent.getStringExtra(key);
        if (value == null || value.trim().isEmpty()) {
            return defaultValue;
        }
        return value.trim();
    }

    private static int intExtra(Intent intent, String key, int defaultValue) {
        return intent == null ? defaultValue : intent.getIntExtra(key, defaultValue);
    }

    private static String hex(byte[] bytes) {
        StringBuilder builder = new StringBuilder(bytes.length * 3);
        for (byte value : bytes) {
            if (builder.length() > 0) {
                builder.append(' ');
            }
            builder.append(String.format(Locale.US, "%02X", value & 0xff));
        }
        return builder.toString();
    }

    private interface ReaderSession extends Closeable {
        InputStream inputStream() throws IOException;
    }

    private static final class FrameworkSerialReaderSession implements ReaderSession {
        private final Object serialPort;
        private final InputStream inputStream;
        private final Method closeMethod;

        private FrameworkSerialReaderSession(Object serialPort, InputStream inputStream, Method closeMethod) {
            this.serialPort = serialPort;
            this.inputStream = inputStream;
            this.closeMethod = closeMethod;
        }

        static FrameworkSerialReaderSession open(Service service, String port, int baud)
                throws ReflectiveOperationException, IOException {
            Object serialManager = service.getSystemService("serial");
            if (serialManager == null) {
                throw new IOException("serial system service unavailable");
            }

            Method getSerialPorts = serialManager.getClass().getMethod("getSerialPorts");
            String[] ports = (String[]) getSerialPorts.invoke(serialManager);
            Log.i(ShyftedDeviceClient.TAG, "LD2410_PROBE SerialManager ports=" + Arrays.toString(ports));

            Method openSerialPort = serialManager.getClass().getMethod("openSerialPort", String.class, int.class);
            Object serialPort = openSerialPort.invoke(serialManager, port, baud);
            if (serialPort == null) {
                throw new IOException("openSerialPort returned null");
            }

            Method getInputStream = serialPort.getClass().getMethod("getInputStream");
            Method close = serialPort.getClass().getMethod("close");
            InputStream inputStream = (InputStream) getInputStream.invoke(serialPort);
            Log.i(ShyftedDeviceClient.TAG, "LD2410_PROBE SerialManager open success port=" + port + " baud=" + baud);
            return new FrameworkSerialReaderSession(serialPort, inputStream, close);
        }

        @Override
        public InputStream inputStream() {
            return inputStream;
        }

        @Override
        public void close() throws IOException {
            try {
                closeMethod.invoke(serialPort);
            } catch (ReflectiveOperationException e) {
                throw new IOException("SerialPort close failed", e);
            }
        }
    }

    private static final class ProcessReaderSession implements ReaderSession {
        private final Process process;

        private ProcessReaderSession(Process process) {
            this.process = process;
        }

        @Override
        public InputStream inputStream() {
            return process.getInputStream();
        }

        @Override
        public void close() {
            process.destroy();
        }
    }

    private static final class ProbeListener implements Ld2410StreamDecoder.Listener {
        int frameCount;
        int nonDataPacketCount;
        private String lastState;
        private long lastLogMs;

        @Override
        public void onFrame(byte[] rawPacket, Ld2410Frame frame) {
            frameCount++;
            String state = frame.toLogString();
            long now = System.currentTimeMillis();
            if (!state.equals(lastState) || now - lastLogMs >= LOG_REPEAT_MS) {
                Log.i(ShyftedDeviceClient.TAG, "LD2410_FRAME count=" + frameCount
                        + " raw=" + hex(rawPacket)
                        + " decoded=\"" + state + "\"");
                lastState = state;
                lastLogMs = now;
            }
        }

        @Override
        public void onNonDataPacket(byte[] rawPacket) {
            nonDataPacketCount++;
            Log.i(ShyftedDeviceClient.TAG, "LD2410_PACKET_NON_DATA count=" + nonDataPacketCount
                    + " raw=" + hex(rawPacket));
        }
    }
}
