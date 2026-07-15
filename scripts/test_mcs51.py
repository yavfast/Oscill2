#!/usr/bin/env python3
"""
MCS-51 decoder tests (Phase 1 of PL_OMS).

Verifies SP_OMS_05_01 `instr_len` totality (all 256 opcodes → {1,2,3}) plus the
named spot-checks (0x02/0x12 → 3, 0x80 → 2, 0x00 → 1, 0xA5 illegal) and a
hand-checked LJMP decode of `02 hi lo`.

Per project rule PythonTestsAreStandaloneScripts: no pytest, runnable as
`python3 scripts/test_mcs51.py`. Prints PASS/FAIL per case, exits non-zero on failure.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'firmware'))

from mcs51 import instr_len, instr_info, decode_stream, ILLEGAL_OPCODE  # noqa: E402

_failures = 0


def check(name, cond):
    global _failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        _failures += 1
    print(f"  [{status}] {name}")


def test_totality():
    print("instr_len totality (all 256 opcodes):")
    ok = all(instr_len(op) in (1, 2, 3) for op in range(256))
    check("every opcode -> {1,2,3}", ok)
    # Named spot-checks from SP_OMS_05_01.
    check("0x02 LJMP -> 3", instr_len(0x02) == 3)
    check("0x12 LCALL -> 3", instr_len(0x12) == 3)
    check("0x80 SJMP -> 2", instr_len(0x80) == 2)
    check("0x00 NOP -> 1", instr_len(0x00) == 1)
    check("0x90 MOV DPTR,#imm16 -> 3", instr_len(0x90) == 3)


def test_kinds():
    print("instr kind classification:")
    check("0x02 -> abs_jump", instr_info(0x02).kind == "abs_jump")
    check("0x12 -> abs_call", instr_info(0x12).kind == "abs_call")
    check("0x01 AJMP -> page_jump", instr_info(0x01).kind == "page_jump")
    check("0x11 ACALL -> page_call", instr_info(0x11).kind == "page_call")
    check("0x80 SJMP -> rel_branch", instr_info(0x80).kind == "rel_branch")
    check("0x74 MOV A,#imm -> other", instr_info(0x74).kind == "other")


def test_illegal():
    print("illegal opcode (0xA5):")
    check("0xA5 illegal flag set", instr_info(ILLEGAL_OPCODE).illegal is True)
    check("only 0xA5 is illegal",
          [op for op in range(256) if instr_info(op).illegal] == [0xA5])


def test_decode_ljmp():
    print("hand-checked LJMP decode (02 0d 83 00):")
    stream = decode_stream(bytes([0x02, 0x0D, 0x83, 0x00]))
    check("2 instructions decoded", len(stream) == 2)
    check("first is LJMP len 3", stream[0].opcode == 0x02 and stream[0].length == 3)
    check("second is NOP len 1 at offset 3", stream[1].opcode == 0x00 and stream[1].length == 1)


if __name__ == "__main__":
    print("=" * 60)
    print("MCS-51 decoder tests (firmware/mcs51.py)")
    print("=" * 60)
    test_totality()
    test_kinds()
    test_illegal()
    test_decode_ljmp()
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} failing case(s))")
        sys.exit(1)
    print("RESULT: PASS (all cases passed)")
