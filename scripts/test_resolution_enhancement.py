#!/usr/bin/env python3
"""
SP_RES — Standalone hardware-free tests against the REAL web_oscill/resolution.py
and the enhancement-settings clamp in web_oscill/device_service.py.

Per project rule PythonTestsAreStandaloneScripts: no pytest, runnable as
`python3 scripts/test_resolution_enhancement.py`. Prints PASS/FAIL per case and
exits non-zero on any failure. All frames are synthetic — no device required.

Covers PL_RES Phase 1/2/3 verification (SP_RES_05_01 / 05_02 / 05_04):
alignment estimator, gate, SMA, compute_enhanced_trace (SNR gain, fallbacks,
edge cases), 16-bit ×257 mV consistency, effective_bits formula, silent clamp.
"""

import math
import os
import sys

import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'web_oscill'))

import resolution  # noqa: E402
from resolution import (  # noqa: E402
    estimate_alignment_offset,
    accept_frame,
    moving_average,
    compute_enhanced_trace,
)
from calculations import samples_from_hex, samples_to_millivolts  # noqa: E402
from device_service import DeviceService  # noqa: E402

_failures = 0

# Deterministic synthetic data (no Math.random equivalent leaking into results).
_RNG = np.random.default_rng(20260715)

# A config exercising the real mV path: 1 V/div, 1 ms/div, 8 divisions.
CONFIG = {
    "v_div": {"v": 1000.0, "u": "mV"},
    "t_div": {"v": 1.0, "u": "ms"},
    "h_divs": 8,
    "enh_enabled": True,
    "enh_depth": 16,
    "enh_sma_window": 1,
}

N = 256
_T = np.arange(N)
_CLEAN = 128 + 90 * np.sin(2 * np.pi * 4 * _T / N)


def check(name, cond):
    global _failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        _failures += 1
    print(f"  [{status}] {name}")


def _noisy_frames(count, noise_std=6.0, cfg_id=7):
    frames = []
    for _ in range(count):
        s = np.clip(np.round(_CLEAN + _RNG.normal(0, noise_std, N)), 0, 255).astype(int)
        frames.append({"samples": s.tolist(), "cfg_id": cfg_id})
    return frames


def test_estimate_alignment_offset():
    print("estimate_alignment_offset:")
    # candidate = reference delayed by +2.4 samples
    cand = np.interp(_T - 2.4, _T, _CLEAN)
    shift, corr = estimate_alignment_offset(cand, _CLEAN, max_lag=20)
    check("known +2.4 shift recovered (+-0.2)", abs(shift - 2.4) < 0.2)
    check("correlation ~1.0 on match", corr > 0.99)
    # uncorrelated random candidate
    rnd = _RNG.uniform(0, 255, N)
    _, corr_r = estimate_alignment_offset(rnd, _CLEAN, max_lag=20)
    check("uncorrelated correlation below threshold", corr_r < 0.7)
    # too-short reference degrades safely
    check("len<4 -> (0,0)", estimate_alignment_offset([1, 2], [1, 2], 1) == (0.0, 0.0))


def test_accept_frame():
    print("accept_frame (gate):")
    check("good match accepted", accept_frame(0.95, 1.0, 20) is True)
    check("false trigger rejected (low corr)", accept_frame(0.4, 0.0, 20) is False)
    check("rejected when shift exceeds max_lag", accept_frame(0.99, 25.0, 20) is False)


def test_moving_average():
    print("moving_average (SMA):")
    step = np.concatenate([np.zeros(10), np.full(10, 200.0)])
    ma = moving_average(step, 5)
    check("length preserved", len(ma) == len(step))
    check("first sample not zero-biased (shrinking edge)", ma[0] == step[0])
    check("last sample not zero-biased", ma[-1] == step[-1])
    check("W<=1 returns input unchanged", moving_average([1.0, 2.0, 3.0], 1) == [1.0, 2.0, 3.0])


def test_compute_enhanced_trace_snr():
    print("compute_enhanced_trace — periodic, noisy (SNR gain):")
    frames = _noisy_frames(16)
    block = compute_enhanced_trace(frames, CONFIG)
    check("averaging_active", block["averaging_active"] is True)
    check("status_reason ok", block["status_reason"] == "ok")
    check("all 16 frames folded in", block["frames_accumulated"] == 16)
    check("length preserved", block["length"] == N)
    dec = samples_from_hex(block["samples_hex"], 2)
    check("decodes to length samples", len(dec) == N)
    avg8 = np.asarray(dec) / 257.0
    resid = np.std(avg8 - _CLEAN)
    single = np.std(np.asarray(frames[0]["samples"]) - _CLEAN)
    # SP_RES_05_02: averaged noise <= single / sqrt(0.9 * accumulated)
    check("SNR gain ~sqrt(N)", resid <= single / math.sqrt(0.9 * block["frames_accumulated"]))
    check("effective_bits_gain == 0.5*log2(N)",
          abs(block["effective_bits_gain"] - 0.5 * math.log2(block["frames_accumulated"])) < 1e-9)
    check("mean_correlation high", block["mean_correlation"] > 0.9)


def test_compute_enhanced_trace_fallbacks():
    print("compute_enhanced_trace — fallbacks:")
    flat = [{"samples": [128] * N, "cfg_id": 1} for _ in range(4)]
    b_flat = compute_enhanced_trace(flat, CONFIG)
    check("flat -> not-periodic", b_flat["status_reason"] == "not-periodic")
    check("not-periodic still renders full length", b_flat["length"] == N)
    check("not-periodic not averaging", b_flat["averaging_active"] is False)

    peak = [{"samples": _noisy_frames(1)[0]["samples"], "cfg_id": 1,
             "samples_peak_min": [0] * N}]
    b_peak = compute_enhanced_trace(peak, CONFIG)
    check("peak frame -> peak-mode", b_peak["status_reason"] == "peak-mode")

    single = _noisy_frames(1)
    b_single = compute_enhanced_trace(single, CONFIG)
    check("single frame -> insufficient-frames", b_single["status_reason"] == "insufficient-frames")
    check("insufficient-frames block still decodes", len(samples_from_hex(b_single["samples_hex"], 2)) == N)

    check("disabled -> no block", compute_enhanced_trace(_noisy_frames(4), {"enh_enabled": False}) is None)
    check("empty window -> no block", compute_enhanced_trace([], CONFIG) is None)


def test_compute_enhanced_trace_edges():
    print("compute_enhanced_trace — edge cases (SP_RES_05_04):")
    frames = _noisy_frames(16)
    b2 = compute_enhanced_trace(frames[:2], {**CONFIG, "enh_depth": 2})
    check("enh_depth=2 folds exactly 2", b2["frames_accumulated"] == 2)
    check("enh_depth=2 gain=0.5", abs(b2["effective_bits_gain"] - 0.5) < 1e-9)

    # Mixed cfg_id / length in window -> only matching frames fold in.
    mixed = _noisy_frames(3, cfg_id=7)
    mixed.append({"samples": _noisy_frames(1, cfg_id=9)[0]["samples"], "cfg_id": 9})   # different cfg
    mixed.append({"samples": [128] * (N // 2), "cfg_id": 7})                            # different length
    b_mixed = compute_enhanced_trace(mixed, CONFIG)
    check("only same-cfg_id+length frames folded", b_mixed["frames_accumulated"] == 3)

    b_sma = compute_enhanced_trace(frames, {**CONFIG, "enh_sma_window": 5})
    check("W>1 -> smoothing_active", b_sma["smoothing_active"] is True)
    check("smoothing preserves length", b_sma["length"] == N)


def test_mv_consistency():
    print("16-bit x257 mV consistency (SP_RES_05_02 / 03_03):")
    raw8 = _noisy_frames(1)[0]["samples"]
    mv8 = samples_to_millivolts(raw8, 8, CONFIG)
    raw16 = resolution._to_fixed16(raw8)
    mv16 = samples_to_millivolts(raw16, 16, CONFIG)
    maxdiff = max(abs(a - b) for a, b in zip(mv8, mv16))
    lsb16 = abs(samples_to_millivolts([1], 16, CONFIG)[0] - samples_to_millivolts([0], 16, CONFIG)[0])
    check("mV(enhanced 16-bit) within one 16-bit LSB of 8-bit", maxdiff <= lsb16 + 1e-9)


def test_apply_config_clamp():
    print("apply_config enhancement clamp (SP_RES_05_01 / 03_01) — real DeviceService._apply_enh_settings:")
    svc = DeviceService.__new__(DeviceService)  # no device / no __init__ side effects
    cfg = {}
    svc._apply_enh_settings(cfg, {"enh_enabled": 1, "enh_depth": 999, "enh_sma_window": 8})
    check("enh_enabled coerced to bool", cfg["enh_enabled"] is True)
    check("enh_depth clamped 999 -> 64", cfg["enh_depth"] == 64)
    check("enh_sma_window 8 -> 7 (forced odd)", cfg["enh_sma_window"] == 7)
    cfg2 = {}
    svc._apply_enh_settings(cfg2, {"enh_depth": 1, "enh_sma_window": 100})
    check("enh_depth clamped 1 -> 2", cfg2["enh_depth"] == 2)
    check("enh_sma_window clamped 100 -> 63", cfg2["enh_sma_window"] == 63)
    cfg3 = {"enh_depth": 32}
    svc._apply_enh_settings(cfg3, {})  # absent keys leave existing values untouched
    check("absent keys leave value untouched", cfg3["enh_depth"] == 32)


def main():
    print("=" * 60)
    print("SP_RES resolution-enhancement tests")
    print("=" * 60)
    test_estimate_alignment_offset()
    test_accept_frame()
    test_moving_average()
    test_compute_enhanced_trace_snr()
    test_compute_enhanced_trace_fallbacks()
    test_compute_enhanced_trace_edges()
    test_mv_consistency()
    test_apply_config_clamp()
    print("=" * 60)
    if _failures:
        print(f"RESULT: {_failures} FAILURE(S)")
        sys.exit(1)
    print("RESULT: ALL PASSED")


if __name__ == "__main__":
    main()
