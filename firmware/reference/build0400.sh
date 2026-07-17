#!/bin/bash
# Build the C8051F340 APP image relocated to 0x0400 — the "behind-bootloader"
# layout (AN778): the interrupt VECTOR TABLE relocates to 0x0400+offset, matching
# how the Oscill app (logical page L=0 @ 0x0400) is laid out. No hardware needed.
#
# Vector relocation is automatic: --code-loc 0x0400 moves area HOME (the vector
# table) to 0x0400, so the reset/ISR LJMPs land at 0x0400, 0x040B, 0x0423, ...
# In a real device the resident bootloader (0x0000-0x03FF, NOT in this image nor
# in the .ofw) forwards each hardware vector with `LJMP 0x0400+offset` to here.
set -e
cd "$(dirname "$0")"
sdcc -mmcs51 --model-small --code-loc 0x0400 --xram-loc 0x1000 ref.c -o ref0400.ihx
# App-only binary: byte 0 == flash 0x0400 (leading 0x0000-0x03FF bootloader gap dropped).
# --gap-fill 0xFF so unwritten bytes read as erased flash (0xFF), like a real device.
sdobjcopy -I ihex -O binary --gap-fill 0xFF ref0400.ihx ref0400_app.bin
echo "built ref0400_app.bin ($(stat -c%s ref0400_app.bin) bytes); byte 0 == flash 0x0400"
echo "first page (512B) = the analogue of the vendor's logical page L=0"
echo "inspect: xxd ref0400_app.bin | head"
