package au.com.shyfted.client;

import java.util.Arrays;
import java.util.Locale;

final class Ld2410Frame {
    final int targetState;
    final int movingDistanceCm;
    final int movingEnergy;
    final int stationaryDistanceCm;
    final int stationaryEnergy;
    final int detectionDistanceCm;
    final int[] movingGateEnergy;
    final int[] stationaryGateEnergy;

    private Ld2410Frame(
            int targetState,
            int movingDistanceCm,
            int movingEnergy,
            int stationaryDistanceCm,
            int stationaryEnergy,
            int detectionDistanceCm,
            int[] movingGateEnergy,
            int[] stationaryGateEnergy
    ) {
        this.targetState = targetState;
        this.movingDistanceCm = movingDistanceCm;
        this.movingEnergy = movingEnergy;
        this.stationaryDistanceCm = stationaryDistanceCm;
        this.stationaryEnergy = stationaryEnergy;
        this.detectionDistanceCm = detectionDistanceCm;
        this.movingGateEnergy = movingGateEnergy;
        this.stationaryGateEnergy = stationaryGateEnergy;
    }

    static Ld2410Frame parse(byte[] body) {
        if (body.length < 13 || u8(body[0]) != 0x02 || u8(body[1]) != 0xaa) {
            return null;
        }

        int targetState = u8(body[2]);
        int movingDistanceCm = le16(body, 3);
        int movingEnergy = u8(body[5]);
        int stationaryDistanceCm = le16(body, 6);
        int stationaryEnergy = u8(body[8]);
        int detectionDistanceCm = le16(body, 9);

        int[] movingGateEnergy = null;
        int[] stationaryGateEnergy = null;
        if (body.length >= 31) {
            movingGateEnergy = readEnergyGates(body, 11);
            stationaryGateEnergy = readEnergyGates(body, 20);
        }

        return new Ld2410Frame(
                targetState,
                movingDistanceCm,
                movingEnergy,
                stationaryDistanceCm,
                stationaryEnergy,
                detectionDistanceCm,
                movingGateEnergy,
                stationaryGateEnergy
        );
    }

    boolean isPresenceDetected() {
        return targetState != 0;
    }

    boolean isMovingTargetDetected() {
        return targetState == 1 || targetState == 3;
    }

    boolean isStationaryTargetDetected() {
        return targetState == 2 || targetState == 3;
    }

    String targetStateName() {
        switch (targetState) {
            case 0:
                return "none";
            case 1:
                return "moving";
            case 2:
                return "stationary";
            case 3:
                return "moving+stationary";
            default:
                return "unknown(" + targetState + ")";
        }
    }

    String toLogString() {
        StringBuilder builder = new StringBuilder()
                .append("Presence=").append(isPresenceDetected())
                .append(" state=").append(targetStateName())
                .append(" moving=").append(isMovingTargetDetected())
                .append(" stationary=").append(isStationaryTargetDetected())
                .append(" moving_distance_m=").append(meters(movingDistanceCm))
                .append(" stationary_distance_m=").append(meters(stationaryDistanceCm))
                .append(" detection_distance_m=").append(meters(detectionDistanceCm))
                .append(" moving_energy=").append(movingEnergy)
                .append(" stationary_energy=").append(stationaryEnergy);

        if (movingGateEnergy != null && stationaryGateEnergy != null) {
            builder.append(" moving_gate_energy=").append(Arrays.toString(movingGateEnergy))
                    .append(" stationary_gate_energy=").append(Arrays.toString(stationaryGateEnergy));
        }
        return builder.toString();
    }

    private static int[] readEnergyGates(byte[] body, int offset) {
        int[] gates = new int[9];
        for (int i = 0; i < gates.length; i++) {
            gates[i] = u8(body[offset + i]);
        }
        return gates;
    }

    private static String meters(int centimeters) {
        return String.format(Locale.US, "%.2f", centimeters / 100.0d);
    }

    private static int le16(byte[] bytes, int offset) {
        return u8(bytes[offset]) | (u8(bytes[offset + 1]) << 8);
    }

    private static int u8(byte value) {
        return value & 0xff;
    }
}
