#!/bin/bash
# Build the C8051F340 reference-structure image (needs: sdcc).
# Purpose: a KNOWN-plaintext 8051 image to (a) study compiled structure and
# (b) validate a recovered keystream later (spike §5.2). No hardware needed.
set -e
cd "$(dirname "$0")"
sdcc -mmcs51 --model-small --code-loc 0x0000 ref.c
makebin -p ref.ihx ref.bin
echo "built ref.bin ($(stat -c%s ref.bin) bytes); listing = ref.rst, map = ref.map, mem = ref.mem"
echo "inspect: xxd ref.bin | head   |   s51 ref.ihx   (simulator)"
