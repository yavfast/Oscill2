"""
Periodic-signal resolution enhancement engine.  [C_RES / SP_RES_02]

On-read coherent sliding-window averaging (align -> gate -> average) of periodic-signal
frames, plus an optional per-frame SMA smoother. Pure functions: no device I/O and no
persistent state (SP_RES_DEC_02) -- numpy in, plain dict/list out. Called from
main.py's /api/frames handler (PL_RES_DEC_01); depends on calculations/converters only
(LayerDependencyDirection).
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import math

import numpy as np

# Accepts either a plain sample sequence or a numpy array (internal working form).
Samples = Union[Sequence[float], np.ndarray]

from calculations import calculate_frequency_and_period, samples_to_hex
from converters import get_time_ms

# [SP_RES_01_03] 255 * 257 == 65535 maps the 8-bit full scale exactly onto the 16-bit
# full scale, preserving ~8 bits of sub-quantization detail recovered by averaging.
_FIXED16_SCALE = 257.0

# [SP_RES_02_03] Internal tuning constant (not user-facing -- Minimality). May be
# re-tuned during Verify against measured trigger jitter.
ACCEPTANCE_THRESHOLD = 0.7


def _to_fixed16(values: Samples) -> List[int]:
    """Scale real-valued 8-bit-domain samples (0..255) to 16-bit fixed-point.

    Each sample x -> clamp(round(x * 257), 0, 65535).  [SP_RES_01_03]
    """
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return []
    scaled = np.clip(np.round(arr * _FIXED16_SCALE), 0, 65535)
    return [int(v) for v in scaled]


def _resample(samples: Samples, shift: float) -> np.ndarray:
    """Linearly resample `samples` onto the reference grid, advanced by `shift`.

    aligned[i] = samples[i + shift] (linear interpolation; edges clamp to endpoints).
    """
    arr = np.asarray(samples, dtype=np.float64)
    n = arr.size
    if n == 0:
        return arr
    grid = np.arange(n, dtype=np.float64)
    return np.interp(grid + shift, grid, arr)


def estimate_alignment_offset(candidate: Samples,
                              reference: Samples,
                              max_lag: int) -> Tuple[float, float]:
    """Find the sub-sample shift best aligning `candidate` to `reference`.  [SP_RES_02_02]

    Cross-correlation over a bounded integer lag window + parabolic sub-sample
    refinement (SP_RES_DEC_01). Returns (shift, correlation):
      * shift        -- sub-sample lag; positive = candidate lags the reference.
      * correlation  -- normalized cross-correlation coefficient at the peak, 0.0..1.0.
    """
    ref = np.asarray(reference, dtype=np.float64)
    cand = np.asarray(candidate, dtype=np.float64)
    n = ref.size
    if n < 4 or cand.size != n:
        return 0.0, 0.0

    max_lag = int(max_lag)
    if max_lag < 1:
        max_lag = 1
    if max_lag > n // 2:
        max_lag = n // 2

    a = cand - cand.mean()
    b = ref - ref.mean()

    corrs = np.zeros(2 * max_lag + 1, dtype=np.float64)
    for k, lag in enumerate(range(-max_lag, max_lag + 1)):
        # Pair reference[i] with candidate[i + lag] over the overlapping index range.
        if lag >= 0:
            bb = b[:n - lag]
            aa = a[lag:]
        else:
            bb = b[-lag:]
            aa = a[:n + lag]
        denom = math.sqrt(float(np.dot(aa, aa)) * float(np.dot(bb, bb)))
        corrs[k] = (float(np.dot(aa, bb)) / denom) if denom > 0.0 else 0.0

    peak_idx = int(np.argmax(corrs))
    peak_lag = peak_idx - max_lag
    # Clamp to the documented 0.0..1.0 range (a best-lag Pearson can go slightly
    # negative for anti-correlated/random inputs; the gate rejects those anyway).
    correlation = max(0.0, float(corrs[peak_idx]))

    # Parabolic sub-sample refinement around the integer peak (guard flat/edge peaks).
    shift = float(peak_lag)
    if 0 < peak_idx < corrs.size - 1:
        c0 = corrs[peak_idx - 1]
        c1 = corrs[peak_idx]
        c2 = corrs[peak_idx + 1]
        denom = c0 - 2.0 * c1 + c2
        if abs(denom) > 1e-12:
            delta = 0.5 * (c0 - c2) / denom
            if -1.0 < delta < 1.0:
                shift = peak_lag + float(delta)

    return shift, correlation


def accept_frame(correlation: float,
                 shift: float,
                 max_lag: int,
                 threshold: float = ACCEPTANCE_THRESHOLD) -> bool:
    """Gate: accept an aligned candidate as a valid instance of the waveform.  [SP_RES_02_03]

    Rejects false triggers / mismatched frames (concept items #4/#5).
    """
    return bool(correlation >= threshold and abs(shift) <= max_lag)


def moving_average(samples: Samples, window: int) -> List[float]:
    """Symmetric moving average over the sample axis.  [SP_RES_02_05]

    Length-preserving; edge windows shrink (no padding), so ends are not biased
    toward zero.
    """
    arr = np.asarray(samples, dtype=np.float64)
    n = arr.size
    if window <= 1 or n == 0:
        return [float(x) for x in arr]
    half = int(window) // 2
    cumsum = np.concatenate(([0.0], np.cumsum(arr)))
    idx = np.arange(n)
    lo = np.maximum(0, idx - half)
    hi = np.minimum(n - 1, idx + half)
    out = (cumsum[hi + 1] - cumsum[lo]) / (hi - lo + 1)
    return [float(x) for x in out]


def _is_peak_mode(frame: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """Peak/min-max envelope mode -- out of initial scope (C_RES_03_02)."""
    if "samples_peak_min" in frame or "samples_peak_max" in frame:
        return True
    return str(config.get("sw_mode", "")).upper() in ("PEAK", "PEAK_HI")


def _t_step_ms(config: Dict[str, Any], sample_count: int) -> float:
    """Time per sample (ms), derived from the actual sample count (peak-mode safe).

    Mirrors calculations.calculate_measurements: t_step = total_time_ms / len(samples).
    """
    h_divs = config.get("h_divs", 8)
    t_div_ms = get_time_ms(config)
    total_time_ms = t_div_ms * h_divs
    return total_time_ms / max(1, sample_count)


def _error_block(newest_samples: Samples, enh_depth: int) -> Dict[str, Any]:
    """Inactive block carrying the 16-bit upscale of the newest frame.  [SP_RES_02_04]"""
    fixed16 = _to_fixed16(newest_samples)
    return {
        "averaging_active": False,
        "smoothing_active": False,
        "status_reason": "error",
        "samples_hex": samples_to_hex(fixed16, 2),
        "sample_bits": 16,
        "sample_bytes": 2,
        "length": len(fixed16),
        "frames_accumulated": 1 if fixed16 else 0,
        "frames_rejected": 0,
        "mean_correlation": 1.0,
        "effective_bits_gain": 0.0,
        "depth_requested": enh_depth,
    }


def compute_enhanced_trace(window: List[Dict[str, Any]],
                           config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Produce the EnhancedBlock on-read from the buffered frame window.  [SP_RES_02_04]

    Pure function: no device I/O, no persistent state (SP_RES_DEC_02). Returns None when
    enhancement is disabled or the window is empty. Never raises -- any internal error
    yields an inactive block with status_reason="error" (mirrors calculations'
    silent-degradation + PythonDeviceServiceWarningsVsExceptions).

    Args:
        window: buffered frames, most-recent-first (window[0] is the reference/newest).
        config: current cached config (v_div, t_div, sw_mode, enh_*, h_divs, ...).
    """
    if not config or not config.get("enh_enabled"):
        return None
    if not window:
        return None

    newest = window[0] or {}
    newest_samples = list(newest.get("samples") or [])
    enh_depth = int(config.get("enh_depth", 16) or 16)

    try:
        base = np.asarray(newest_samples, dtype=np.float64)
        n = base.size
        window_size = int(config.get("enh_sma_window", 1) or 1)
        newest_cfg = newest.get("cfg_id")

        reason = "ok"
        accumulated = 1
        rejected = 0
        corr_sum = 0.0
        corr_n = 0

        if n == 0:
            reason = "insufficient-frames"
        elif _is_peak_mode(newest, config):
            # [C_RES_03_02] Peak/min-max envelope averaging is out of initial scope.
            reason = "peak-mode"
        else:
            t_step_ms = _t_step_ms(config, n)
            freq_period = calculate_frequency_and_period(newest_samples, t_step_ms)
            period_s = freq_period.get("period")
            if not period_s or period_s <= 0 or t_step_ms <= 0:
                reason = "not-periodic"
            else:
                period_samples = (period_s * 1000.0) / t_step_ms
                max_lag = int(round(period_samples / 2.0))
                max_lag = max(1, min(max_lag, n // 2))

                ref = base
                acc_sum = base.copy()
                # [SP_RES_03_02] Only same-cfg_id, same-length frames; at most enh_depth.
                for frame in window[1:]:
                    if accumulated >= enh_depth:
                        break
                    f_samples = frame.get("samples") or []
                    if frame.get("cfg_id") != newest_cfg or len(f_samples) != n:
                        continue
                    shift, corr = estimate_alignment_offset(f_samples, ref, max_lag)
                    if accept_frame(corr, shift, max_lag):
                        acc_sum = acc_sum + _resample(f_samples, shift)
                        accumulated += 1
                        corr_sum += corr
                        corr_n += 1
                    else:
                        rejected += 1

                if accumulated >= 2:
                    base = acc_sum / accumulated
                else:
                    reason = "insufficient-frames"

        smoothing_active = window_size > 1
        out = moving_average(base, window_size) if smoothing_active else base
        averaging_active = (reason == "ok" and accumulated >= 2)
        samples16 = _to_fixed16(out)

        return {
            "averaging_active": averaging_active,
            "smoothing_active": smoothing_active,
            "status_reason": reason,
            "samples_hex": samples_to_hex(samples16, 2),
            "sample_bits": 16,
            "sample_bytes": 2,
            "length": len(samples16),
            "frames_accumulated": accumulated,
            "frames_rejected": rejected,
            "mean_correlation": (corr_sum / corr_n) if corr_n > 0 else 1.0,
            "effective_bits_gain": 0.5 * math.log2(max(1, accumulated)),
            "depth_requested": enh_depth,
        }
    except Exception:
        # [SP_RES_02_04] Never raise: degrade to an inactive, still-renderable block.
        return _error_block(newest_samples, enh_depth)
