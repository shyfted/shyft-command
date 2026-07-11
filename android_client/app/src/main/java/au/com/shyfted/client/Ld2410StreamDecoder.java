package au.com.shyfted.client;

import java.io.ByteArrayOutputStream;

final class Ld2410StreamDecoder {
    interface Listener {
        void onFrame(byte[] rawPacket, Ld2410Frame frame);

        void onNonDataPacket(byte[] rawPacket);
    }

    private static final byte[] DATA_HEADER = new byte[]{
            (byte) 0xf4, (byte) 0xf3, (byte) 0xf2, (byte) 0xf1
    };
    private static final int MAX_PACKET_LENGTH = 128;

    private final ByteArrayOutputStream buffer = new ByteArrayOutputStream();

    void accept(byte[] data, int length, Listener listener) {
        buffer.write(data, 0, length);
        byte[] bytes = buffer.toByteArray();
        int offset = 0;

        while (true) {
            int header = findHeader(bytes, offset);
            if (header < 0) {
                resetBuffer(bytes, Math.max(0, bytes.length - (DATA_HEADER.length - 1)));
                return;
            }
            if (bytes.length - header < 6) {
                resetBuffer(bytes, header);
                return;
            }

            int bodyLength = u8(bytes[header + 4]) | (u8(bytes[header + 5]) << 8);
            if (bodyLength <= 0 || bodyLength > MAX_PACKET_LENGTH) {
                offset = header + 1;
                continue;
            }

            int packetLength = 6 + bodyLength;
            if (bytes.length - header < packetLength) {
                resetBuffer(bytes, header);
                return;
            }

            byte[] rawPacket = copyOfRange(bytes, header, header + packetLength);
            byte[] body = copyOfRange(bytes, header + 6, header + packetLength);
            Ld2410Frame frame = Ld2410Frame.parse(body);
            if (frame != null) {
                listener.onFrame(rawPacket, frame);
            } else {
                listener.onNonDataPacket(rawPacket);
            }
            offset = header + packetLength;

            if (offset >= bytes.length) {
                buffer.reset();
                return;
            }
        }
    }

    private void resetBuffer(byte[] bytes, int start) {
        buffer.reset();
        if (start < bytes.length) {
            buffer.write(bytes, start, bytes.length - start);
        }
    }

    private static int findHeader(byte[] bytes, int start) {
        for (int i = start; i <= bytes.length - DATA_HEADER.length; i++) {
            boolean match = true;
            for (int j = 0; j < DATA_HEADER.length; j++) {
                if (bytes[i + j] != DATA_HEADER[j]) {
                    match = false;
                    break;
                }
            }
            if (match) {
                return i;
            }
        }
        return -1;
    }

    private static byte[] copyOfRange(byte[] bytes, int start, int end) {
        byte[] copy = new byte[end - start];
        System.arraycopy(bytes, start, copy, 0, copy.length);
        return copy;
    }

    private static int u8(byte value) {
        return value & 0xff;
    }
}
