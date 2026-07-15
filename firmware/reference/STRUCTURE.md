# C8051F340 reference image — realistic oscilloscope structure (SDCC 4.5.0)

Built with `./build.sh` (@0x0000) or `./build0400.sh` (@0x0400, app-behind-bootloader). No hardware.
A **known-plaintext** 8051 image whose code+data layout mirrors a real Oscill firmware, to (a) recognise
the vendor's plaintext structure once decrypted and (b) validate a recovered keystream (spike §5.2).
`ref.c` uses the project's **real** OBEX register names + protocol codes (skills/obex_protocol,
`web_oscill/oscill_client.py`). Image ≈ **1645 B (~4 pages)**.

## Memory map (relocated @0x0400 build — `ref0400_app.bin`, byte 0 == flash 0x0400)
```
0x0400  reset      LJMP 0x04A4        ─┐
0x0403  INT0       LJMP <ext0>         │ interrupt VECTOR TABLE, 8-byte spacing
0x040B  Timer0     LJMP <timebase>     │  (0x03+8·n); defined -> LJMP, unused -> RETI/0xFF
0x0423  UART0      LJMP <obex I/O>     │  7 live ISRs: INT0/Timer0/UART0/Timer2/USB0/ADC0/PCA0
0x042B  Timer2     LJMP <sweep>        │
0x0443  USB0       LJMP <usbxpress>    │
0x0453  ADC0-EOC   LJMP <sampler>      │
0x045B  PCA0       LJMP <pwm>         ─┘
0x04A4  __sdcc_gsinit_startup          C runtime (clear iRAM, init globals)
0x0776  main()                         acquire -> detect_segments -> adc_to_mv -> hex_encode -> OBEX
0x086C  banner   "Oscill.com oscilloscope\r\n"   ┐
0x0886  dev_name "Uosc" / "1.26" / "1.2"          │ ASCII cribs (== the .ofw header cribs)
0x0894  reg_table  {name,type,addr} × 12          │ OBEX regs: VSW VSN VNM VHW QS TS RS M1 O1 AP RT AVG
0x08E8  cal_table  8-byte records × 8 ranges       │ 0xFF at offset 4 (mirrors vendor ff@lat)
0x0928  hexlut   "0123456789ABCDEF"                │ hex-encode LUT (HTTP/OBEX transport)
0x0939  sine_lut 256-byte waveform table           │ timebase/display LUT
0x0A39  usb_desc USB dev/cfg descriptor            ┘ SiLabs VID 0x10C4
0x0A6C  end
```
(The @0x0000 `build.sh` variant is identical but with LJMP targets 0x00xx and no leading bootloader gap.)

## Structural facts to compare with the encrypted vendor `.ofw`
1. **Vector table = 8-byte spacing** (0x03+8·n) — same period as the vendor's stride-8 mask lattice.
   Reset+7 ISR `LJMP`s; unused slots `RETI(0x32)`/`0xFF`. At 0x0400 only the LJMP target high byte
   shifts vs the 0x0000 build (`02 00 .. → 02 04 ..`).
2. **8-byte-record data tables with 0xFF at offset 4** = the vendor `ff@lat` pages (CRC=D3/F5, L=14–24):
   ```
   0x08E8: 00 04 00 00 FF 01 00 05  9A 03 10 00 FF 01 01 A5  ...
                       ^^ reserved 0xFF at offset 4, exactly the vendor's offset-4-mod-8 lattice
   ```
   → confirms those pages are **real 8-byte-record data tables** (e.g. per-range calibration), not blank.
3. **ASCII cribs** sit as short plaintext runs — `Oscill.com oscilloscope`, `Uosc`, `1.26` (the *same*
   strings as the `.ofw` header) and the OBEX register names `VSW/VSN/VNM/VHW/QS/TS/RS/M1/O1/AP/RT/AVG`.
   `strings ref0400_app.bin` lists them — a correct decrypt of the vendor image must expose these.
4. **Entropy = 6.77 b/byte** (real code+data) vs the encrypted vendor payload's **7.98** → a correct
   keystream MUST drop entropy toward ~5–6 and expose the cribs. This is the pass/fail test for a mask.
5. **Register table shape** `{char name[..], u8 type, u16 addr}` and the OBEX type codes (`F0`=2-byte,
   `F1`=4-byte, `B1`=1-byte) show how the device's property table is likely laid out in flash.

## Fidelity / limits
SDCC output is a **strong structural** reference, not byte-identical to the vendor. Byte-exact match
needs the vendor's compiler (**Keil C51**, via SiLabs Simplicity Studio). The reference cannot decrypt
the vendor image; it recognises structure and validates a keystream once a known page (C2) yields one.

## Files
`ref.c` (source) · `build.sh` (@0x0000) · `build0400.sh` (@0x0400, app-only) · outputs
`ref*.bin/.ihx/.rst/.map/.mem`, `ref0400_app.bin` are regenerable.
