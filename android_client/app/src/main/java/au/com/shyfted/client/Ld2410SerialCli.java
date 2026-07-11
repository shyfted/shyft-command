package au.com.shyfted.client;

import android.os.IBinder;
import android.os.ParcelFileDescriptor;

import java.io.File;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.util.Locale;

public final class Ld2410SerialCli {
    private Ld2410SerialCli() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 1 || "help".equals(args[0])) {
            printUsage();
            return;
        }

        if ("inspect".equals(args[0])) {
            inspect();
            return;
        }

        if (!"probe".equals(args[0]) || args.length < 4) {
            printUsage();
            return;
        }

        String port = args[1];
        int baud = Integer.parseInt(args[2]);
        int durationSeconds = Integer.parseInt(args[3]);
        probe(port, baud, durationSeconds);
    }

    private static void inspect() throws Exception {
        Class<?> serviceManagerClass = Class.forName("android.os.ServiceManager");
        Method getService = serviceManagerClass.getMethod("getService", String.class);
        IBinder binder = (IBinder) getService.invoke(null, "serial");
        System.out.println("serial_binder=" + binder);

        Class<?> stubClass = Class.forName("android.hardware.ISerialManager$Stub");
        Method asInterface = stubClass.getMethod("asInterface", IBinder.class);
        Object serialService = asInterface.invoke(null, binder);
        System.out.println("serial_service=" + serialService);
        for (Method method : serialService.getClass().getMethods()) {
            if (method.getName().toLowerCase(Locale.US).contains("serial")
                    || method.getName().toLowerCase(Locale.US).contains("port")) {
                System.out.println("service_method=" + method);
            }
        }

        Class<?> serialPortClass = Class.forName("android.hardware.SerialPort");
        System.out.println("serial_port_class=" + serialPortClass);
        for (Constructor<?> constructor : serialPortClass.getDeclaredConstructors()) {
            System.out.println("serial_port_constructor=" + constructor);
        }
        for (Method method : serialPortClass.getDeclaredMethods()) {
            System.out.println("serial_port_method=" + method);
        }
    }

    private static void probe(String port, int baud, int durationSeconds) throws Exception {
        System.out.println("LD2410_CLI start port=" + port + " baud=" + baud
                + " duration_seconds=" + durationSeconds);

        ParcelFileDescriptor pfd = ParcelFileDescriptor.open(
                new File(port),
                ParcelFileDescriptor.MODE_READ_WRITE);
        if (pfd == null) {
            throw new IllegalStateException("direct ParcelFileDescriptor.open returned null for " + port);
        }
        System.out.println("LD2410_CLI direct_pfd_open_success fd=" + pfd.getFd());

        Class<?> serialPortClass = Class.forName("android.hardware.SerialPort");
        Constructor<?> constructor = serialPortClass.getDeclaredConstructor(String.class);
        constructor.setAccessible(true);
        Object serialPort = constructor.newInstance(port);

        Method open = serialPortClass.getDeclaredMethod("open", ParcelFileDescriptor.class, int.class);
        open.setAccessible(true);
        open.invoke(serialPort, pfd, baud);
        System.out.println("LD2410_CLI serial_port_open_success");

        Method close = serialPortClass.getMethod("close");
        Method read = serialPortClass.getMethod("read", ByteBuffer.class);

        Ld2410StreamDecoder decoder = new Ld2410StreamDecoder();
        CliListener listener = new CliListener();
        long deadline = System.currentTimeMillis() + durationSeconds * 1000L;
        byte[] buffer = new byte[256];
        ByteBuffer byteBuffer = ByteBuffer.allocateDirect(buffer.length);
        try {
            while (System.currentTimeMillis() < deadline) {
                byteBuffer.clear();
                int count = (Integer) read.invoke(serialPort, byteBuffer);
                if (count < 0) {
                    break;
                }
                if (count > 0) {
                    byteBuffer.flip();
                    byteBuffer.get(buffer, 0, count);
                    decoder.accept(buffer, count, listener);
                }
            }
        } finally {
            close.invoke(serialPort);
        }

        System.out.println("LD2410_CLI stop frames=" + listener.frameCount
                + " non_data_packets=" + listener.nonDataPacketCount);
    }

    private static Object serialService() throws Exception {
        Class<?> serviceManagerClass = Class.forName("android.os.ServiceManager");
        Method getService = serviceManagerClass.getMethod("getService", String.class);
        IBinder binder = (IBinder) getService.invoke(null, "serial");
        if (binder == null) {
            throw new IllegalStateException("serial service unavailable");
        }

        Class<?> stubClass = Class.forName("android.hardware.ISerialManager$Stub");
        Method asInterface = stubClass.getMethod("asInterface", IBinder.class);
        return asInterface.invoke(null, binder);
    }

    private static void printUsage() {
        System.out.println("Usage:");
        System.out.println("  app_process /system/bin au.com.shyfted.client.Ld2410SerialCli inspect");
        System.out.println("  app_process /system/bin au.com.shyfted.client.Ld2410SerialCli probe /dev/ttyS3 256000 45");
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

    private static final class CliListener implements Ld2410StreamDecoder.Listener {
        int frameCount;
        int nonDataPacketCount;
        private String lastState;

        @Override
        public void onFrame(byte[] rawPacket, Ld2410Frame frame) {
            frameCount++;
            String state = frame.toLogString();
            if (!state.equals(lastState)) {
                System.out.println("LD2410_FRAME count=" + frameCount
                        + " raw=" + hex(rawPacket)
                        + " decoded=\"" + state + "\"");
                lastState = state;
            }
        }

        @Override
        public void onNonDataPacket(byte[] rawPacket) {
            nonDataPacketCount++;
            System.out.println("LD2410_PACKET_NON_DATA count=" + nonDataPacketCount
                    + " raw=" + hex(rawPacket));
        }
    }
}
