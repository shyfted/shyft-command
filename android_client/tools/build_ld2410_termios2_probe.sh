#!/usr/bin/env bash
set -euo pipefail

NDK_DIR="${NDK_DIR:-/private/tmp/android-ndk-r26d}"
TOOLCHAIN="$NDK_DIR/toolchains/llvm/prebuilt/darwin-x86_64/bin"
CC="$TOOLCHAIN/aarch64-linux-android23-clang"
OUT="${1:-/private/tmp/ld2410_termios2_probe}"

"$CC" -Wall -Wextra -O2 \
  tools/ld2410_termios2_probe.c \
  -o "$OUT"

echo "$OUT"
