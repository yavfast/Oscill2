"""MCS-51 (8051) instruction decoder — length/kind map used as a hard signal.

Canonical, static 256-entry opcode table (SP_OMS_DEC_02): every opcode maps to a
fixed instruction length {1,2,3} and a branch/call `kind`. `0xA5` is the single
reserved (illegal) opcode. No runtime disassembler dependency, no I/O — the table
is a module constant, so decoding is identical across runs (determinism, SP_OMS_05_02).

Used by the .ofw mask solver's S1 (illegal opcode), S2 (instruction-stream tiling)
and S3 (operand range) signals. See docs/ofw_mask_solver.sp.md#SP_OMS_01_02 / #SP_OMS_02_05.

v1 (L=0 vector table) consumes `instr_info` (kind==abs_jump gates the LJMP slot; `illegal`
is S1). `instr_len` and `decode_stream` are the SP_OMS_02_05 contract retained for the
deferred multi-page instruction-boundary decode (PL_OMS Backlog).
"""
# [SP_OMS_01_02] Instr8051 · [SP_OMS_02_05] decode_stream / instr_len
from collections import namedtuple

# One decoded-instruction descriptor. Immutable → safe to cache/return.
Instr8051 = namedtuple("Instr8051", ["opcode", "length", "kind", "illegal"])

ILLEGAL_OPCODE = 0xA5  # the one reserved MCS-51 opcode (S1)

# Canonical MCS-51 instruction lengths, 16 rows of 16 (opcode = row*16 + col).
# Hand-encoded from the Intel MCS-51 manual; row comments name the notable slots.
# Row constant across runs → part of the determinism guarantee.
LEN_TABLE = (
    # 0x00: NOP  AJMP LJMP RR  INCA INCd INC@0 INC@1  INC R0..R7
    1, 2, 3, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    # 0x10: JBC  ACALL LCALL RRC DECA DECd DEC@0 DEC@1  DEC R0..R7
    3, 2, 3, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    # 0x20: JB   AJMP RET  RL  ADD# ADDd ADD@0 ADD@1  ADD Rn
    3, 2, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    # 0x30: JNB  ACALL RETI RLC ADDC# ADDCd ADDC@ ADDC@ ADDC Rn
    3, 2, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    # 0x40: JC   AJMP ORLd,A ORLd,# ORL# ORLd ORL@ ORL@  ORL Rn
    2, 2, 2, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    # 0x50: JNC  ACALL ANLd,A ANLd,# ANL# ANLd ANL@ ANL@  ANL Rn
    2, 2, 2, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    # 0x60: JZ   AJMP XRLd,A XRLd,# XRL# XRLd XRL@ XRL@  XRL Rn
    2, 2, 2, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    # 0x70: JNZ  ACALL ORLC JMP@ MOVA# MOVd# MOV@0# MOV@1#  MOV Rn,#
    2, 2, 2, 1, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    # 0x80: SJMP AJMP ANLC MOVCpc DIV MOVdd MOVd@0 MOVd@1  MOV d,Rn
    2, 2, 2, 1, 1, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    # 0x90: MOVdptr# ACALL MOVbit,C MOVCdptr SUBB# SUBBd SUBB@ SUBB@  SUBB Rn
    3, 2, 2, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    # 0xA0: ORLC/ AJMP MOVC,bit INCdptr MUL A5* MOV@0,d MOV@1,d  MOV Rn,d
    2, 2, 2, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    # 0xB0: ANLC/ ACALL CPLbit CPLC CJNEa# CJNEad CJNE@0 CJNE@1  CJNE Rn,#
    2, 2, 2, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    # 0xC0: PUSH AJMP CLRbit CLRC SWAP XCHd XCH@0 XCH@1  XCH Rn
    2, 2, 2, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    # 0xD0: POP  ACALL SETBbit SETBC DA DJNZd XCHD@0 XCHD@1  DJNZ Rn
    2, 2, 2, 1, 1, 3, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2,
    # 0xE0: MOVXdptr AJMP MOVX@0 MOVX@1 CLRA MOVAd MOVA@0 MOVA@1  MOV A,Rn
    1, 2, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    # 0xF0: MOVX@dptr ACALL MOVX@0 MOVX@1 CPLA MOVdA MOV@0A MOV@1A  MOV Rn,A
    1, 2, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
)
assert len(LEN_TABLE) == 256

# Branch/call opcode → kind. Only these gate S3 (operand range); all others = "other".
_ABS_JUMP = {0x02}                                             # LJMP addr16
_ABS_CALL = {0x12}                                             # LCALL addr16
_PAGE_JUMP = {0x01, 0x21, 0x41, 0x61, 0x81, 0xA1, 0xC1, 0xE1}  # AJMP addr11
_PAGE_CALL = {0x11, 0x31, 0x51, 0x71, 0x91, 0xB1, 0xD1, 0xF1}  # ACALL addr11
_REL_BRANCH = (
    {0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80}           # JBC/JB/JNB/JC/JNC/JZ/JNZ/SJMP
    | {0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF}  # CJNE
    | {0xD5, 0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF}   # DJNZ
)


def _kind_of(op):
    if op in _ABS_JUMP:
        return "abs_jump"
    if op in _ABS_CALL:
        return "abs_call"
    if op in _PAGE_JUMP:
        return "page_jump"
    if op in _PAGE_CALL:
        return "page_call"
    if op in _REL_BRANCH:
        return "rel_branch"
    return "other"


# Precomputed 256-entry descriptor table (built once at import → deterministic).
KIND_TABLE = tuple(_kind_of(op) for op in range(256))
_INSTR_TABLE = tuple(
    Instr8051(op, LEN_TABLE[op], KIND_TABLE[op], op == ILLEGAL_OPCODE)
    for op in range(256)
)


def instr_len(opcode: int) -> int:
    """Total instruction length in bytes for `opcode` (0..255 → {1,2,3}). Never raises."""
    return LEN_TABLE[opcode & 0xFF]


def instr_info(opcode: int) -> Instr8051:
    """Return the Instr8051 descriptor (length + kind + illegal flag) for `opcode`."""
    return _INSTR_TABLE[opcode & 0xFF]


def decode_stream(plain: bytes, start: int = 0) -> list:
    """Greedy linear decode of `plain` (bytes) from `start`.

    Returns a list of Instr8051, walking instruction boundaries by length. A
    trailing opcode whose operands run past the buffer is still emitted (its
    length is the canonical length; the caller sees the boundary overshoot).
    """
    out = []
    i = start
    n = len(plain)
    while i < n:
        info = instr_info(plain[i])
        out.append(info)
        i += info.length
    return out


if __name__ == "__main__":
    # Quick self-report: totality + a hand-checked LJMP decode.
    lens = {instr_len(op) for op in range(256)}
    print(f"instr_len range over 0..255: {sorted(lens)} (expect [1, 2, 3])")
    print(f"0x02 LJMP  len={instr_len(0x02)} kind={instr_info(0x02).kind}")
    print(f"0x12 LCALL len={instr_len(0x12)} kind={instr_info(0x12).kind}")
    print(f"0xA5 illegal={instr_info(0xA5).illegal}")
    demo = decode_stream(bytes([0x02, 0x0D, 0x83, 0x00]))
    print(f"decode 02 0d 83 00 -> {[(hex(x.opcode), x.length) for x in demo]}")
