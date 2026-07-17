# RPi 4B C2 programmer for C8051F41x (`c2_rpi.c`)

Fast C bit-bang of the Silicon Labs **C2 (2-wire)** debug/programming interface on a **Raspberry Pi 4B**
(BCM2711), talking to the Oscill scope's **C8051F41x** MCU. Direct `/dev/gpiomem` register access,
`SCHED_FIFO`+`mlockall` — fast enough to win the `reset→FPCTL-halt` race that a Python bit-bang loses.

This is the **counterpart to the Arduino sketches** (`firmware/arduino_c2*`), which failed on 5 V↔3.3 V
levels (Uno) and PIO/turnaround (Due). RPi GPIO is 3.3 V native → direct connection, no level shifter.

## Wiring (3.3 V direct — NO resistors / level shifter)
| Scope pad | Signal | RPi (BCM) | RPi phys pin |
|-----------|--------|-----------|--------------|
| **-RFS**  | C2CK (=/RST) | GPIO23 | 16 |
| **C2Dat** | C2D (=P2.0)  | GPIO24 | 18 |
| **GND**   | GND | — | 20 (or 6/9/14/25/34/39) |
| +3V3      | VDD | — | **do NOT connect** (scope self-powered) |

Override pins via env: `C2_CK=23 C2_D=24 C2_CHIP=0`. Strobe timing: `C2_TLOW`/`C2_THIGH` (ns).

## Build & run (on the RPi)
```sh
gcc -O2 -o c2_rpi c2_rpi.c
sudo ./c2_rpi id                 # non-destructive: read Device ID x6 (expect 0x0C / Rev 0x02)
sudo ./c2_rpi halt [addr] [len]  # FPCTL halt + FPDAT Get Version + guarded Block Read
                                 #   -> FREEZES the scope (power-cycle to recover)
```
`sudo` is for `SCHED_FIFO`/`mlockall` (GPIO itself is in the `gpio` group). Scope USB stays on the
PC (cp210x) for OBEX monitoring — `scripts/test_connect.py` (needs `sudo modprobe cp210x` +
`echo 10c4 840e > /sys/bus/usb-serial/drivers/cp210x/new_id`).

## Erase-safety
Only ever issues FPDAT `0x06` (Block Read); Block-Read args are gated on command status `0x0D`;
length passed by caller (never `0x03`/`0x07`/`0x08`). No erase/write path exists in this file.

## Findings (2026-07-17, verified on live hardware)
- **C2 fully works:** Device ID `0x0C` reliable; **FPCTL-halt holds**; AR status `0x00`, Get Version `0x0D`.
- **🔒 Flash readback is LOCKED:** Block Read (0x06) is accepted (`st1=0x0D`) but reading flash returns
  a fixed error (`st2=0x03`) and **resets the device** — only flash-reads reset it, identically at
  0x0000/0x4000 and even for 1 byte. Classic flash-security readback-lock signature.
- **Consequence:** a plain C2 flash dump is impossible → ofw-mask **Path A** (known-plaintext →
  keystream) is closed without a **voltage-glitch** bypass. See `docs/arduino_c2_programmer.md` §9
  and `.dev_flow/tasks/task_C2_ARDUINO.md`.

## Notes for reuse
- **Why C, not Python:** C2CK-low must stay < 5 µs (else spurious /RST) and the reset→halt must beat
  the firmware reclaiming P2.0. Python (lgpio/pigpio) is too slow/jittery; register-level C wins.
- Halt uses fast strobes (300/500 ns) to win the race, then the FPDAT phase slows down (F41x "prefers
  more time"). The program leaves C2CK high on exit so the scope isn't held in reset.
- BCM2711-specific register offsets (`/dev/gpiomem`) — **Pi 4B only**; Pi 5 (RP1) differs.
