#include <asm-generic/ioctls.h>
#include <asm-generic/termbits.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#define MAX_PACKET_LENGTH 128
#define BUFFER_LENGTH 1024

static long now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long) ts.tv_sec * 1000L + ts.tv_nsec / 1000000L;
}

static int u16le(const uint8_t *bytes, int offset) {
    return bytes[offset] | (bytes[offset + 1] << 8);
}

static const char *state_name(int state) {
    switch (state) {
        case 0:
            return "none";
        case 1:
            return "moving";
        case 2:
            return "stationary";
        case 3:
            return "moving+stationary";
        default:
            return "unknown";
    }
}

static void print_hex(const uint8_t *bytes, int length) {
    for (int i = 0; i < length; i++) {
        if (i > 0) {
            putchar(' ');
        }
        printf("%02X", bytes[i]);
    }
}

static int find_header(const uint8_t *bytes, int length, int start) {
    static const uint8_t header[] = {0xf4, 0xf3, 0xf2, 0xf1};
    for (int i = start; i <= length - (int) sizeof(header); i++) {
        if (memcmp(bytes + i, header, sizeof(header)) == 0) {
            return i;
        }
    }
    return -1;
}

static void parse_packet(const uint8_t *raw, int raw_length, int *frame_count, int *last_state) {
    const uint8_t *body = raw + 6;
    int body_length = raw_length - 6;
    if (body_length < 13 || body[0] != 0x02 || body[1] != 0xaa) {
        printf("LD2410_PACKET_NON_DATA raw=");
        print_hex(raw, raw_length);
        printf("\n");
        fflush(stdout);
        return;
    }

    int state = body[2];
    int moving_distance_cm = u16le(body, 3);
    int moving_energy = body[5];
    int stationary_distance_cm = u16le(body, 6);
    int stationary_energy = body[8];
    int detection_distance_cm = u16le(body, 9);
    bool presence = state != 0;
    bool moving = state == 1 || state == 3;
    bool stationary = state == 2 || state == 3;

    (*frame_count)++;
    if (state == *last_state && *frame_count > 1) {
        return;
    }
    *last_state = state;

    printf("LD2410_FRAME count=%d raw=", *frame_count);
    print_hex(raw, raw_length);
    printf(" decoded=\"Presence=%s state=%s moving=%s stationary=%s "
           "moving_distance_m=%.2f stationary_distance_m=%.2f detection_distance_m=%.2f "
           "moving_energy=%d stationary_energy=%d\"\n",
           presence ? "true" : "false",
           state_name(state),
           moving ? "true" : "false",
           stationary ? "true" : "false",
           moving_distance_cm / 100.0,
           stationary_distance_cm / 100.0,
           detection_distance_cm / 100.0,
           moving_energy,
           stationary_energy);
    fflush(stdout);
}

static int configure_termios2(int fd, int baud) {
    struct termios2 tio;
    if (ioctl(fd, TCGETS2, &tio) < 0) {
        perror("TCGETS2");
        return -1;
    }

    tio.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL | IXON | IXOFF | IXANY);
    tio.c_oflag &= ~OPOST;
    tio.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
    tio.c_cflag &= ~(CBAUD | CSIZE | PARENB | CSTOPB | CRTSCTS);
    tio.c_cflag |= BOTHER | CS8 | CLOCAL | CREAD;
    tio.c_ispeed = baud;
    tio.c_ospeed = baud;
    tio.c_cc[VMIN] = 0;
    tio.c_cc[VTIME] = 5;

    if (ioctl(fd, TCSETS2, &tio) < 0) {
        perror("TCSETS2");
        return -1;
    }
    return 0;
}

static void decode_bytes(uint8_t *buffer, int *buffer_length, const uint8_t *data, int data_length,
                         int *frame_count, int *last_state) {
    if (*buffer_length + data_length > BUFFER_LENGTH) {
        int keep = *buffer_length < 3 ? *buffer_length : 3;
        memmove(buffer, buffer + *buffer_length - keep, keep);
        *buffer_length = keep;
    }
    memcpy(buffer + *buffer_length, data, data_length);
    *buffer_length += data_length;

    int offset = 0;
    while (true) {
        int header = find_header(buffer, *buffer_length, offset);
        if (header < 0) {
            int keep = *buffer_length < 3 ? *buffer_length : 3;
            memmove(buffer, buffer + *buffer_length - keep, keep);
            *buffer_length = keep;
            return;
        }
        if (*buffer_length - header < 6) {
            memmove(buffer, buffer + header, *buffer_length - header);
            *buffer_length -= header;
            return;
        }

        int body_length = u16le(buffer, header + 4);
        if (body_length <= 0 || body_length > MAX_PACKET_LENGTH) {
            offset = header + 1;
            continue;
        }

        int packet_length = 6 + body_length;
        if (*buffer_length - header < packet_length) {
            memmove(buffer, buffer + header, *buffer_length - header);
            *buffer_length -= header;
            return;
        }

        parse_packet(buffer + header, packet_length, frame_count, last_state);
        offset = header + packet_length;
        if (offset >= *buffer_length) {
            *buffer_length = 0;
            return;
        }
    }
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "Usage: %s /dev/ttyS3 256000 45\n", argv[0]);
        return 2;
    }

    const char *port = argv[1];
    int baud = atoi(argv[2]);
    int duration_seconds = atoi(argv[3]);

    printf("LD2410_NATIVE start port=%s baud=%d duration_seconds=%d\n", port, baud, duration_seconds);
    fflush(stdout);

    int fd = open(port, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) {
        perror("open");
        return 1;
    }
    printf("LD2410_NATIVE open_success fd=%d\n", fd);
    fflush(stdout);

    if (configure_termios2(fd, baud) != 0) {
        close(fd);
        return 1;
    }
    printf("LD2410_NATIVE termios2_success\n");
    fflush(stdout);

    uint8_t buffer[BUFFER_LENGTH];
    int buffer_length = 0;
    uint8_t read_buffer[256];
    int frame_count = 0;
    int raw_chunks = 0;
    long total_bytes = 0;
    int last_state = -1;
    long deadline = now_ms() + (long) duration_seconds * 1000L;

    while (now_ms() < deadline) {
        struct pollfd pfd = {.fd = fd, .events = POLLIN, .revents = 0};
        int poll_result = poll(&pfd, 1, 500);
        if (poll_result < 0) {
            if (errno == EINTR) {
                continue;
            }
            perror("poll");
            break;
        }
        if (poll_result == 0 || !(pfd.revents & POLLIN)) {
            continue;
        }

        ssize_t count = read(fd, read_buffer, sizeof(read_buffer));
        if (count < 0) {
            if (errno == EAGAIN || errno == EINTR) {
                continue;
            }
            perror("read");
            break;
        }
        if (count > 0) {
            total_bytes += count;
            if (raw_chunks < 5) {
                raw_chunks++;
                printf("LD2410_NATIVE_RAW chunk=%d bytes=%zd data=", raw_chunks, count);
                print_hex(read_buffer, (int) count);
                printf("\n");
                fflush(stdout);
            }
            decode_bytes(buffer, &buffer_length, read_buffer, (int) count, &frame_count, &last_state);
        }
    }

    close(fd);
    printf("LD2410_NATIVE stop bytes=%ld frames=%d\n", total_bytes, frame_count);
    fflush(stdout);
    return 0;
}
