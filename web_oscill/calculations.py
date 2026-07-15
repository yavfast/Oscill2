"""
Mathematical calculations and data processing for oscilloscope measurements.
"""
from typing import List, Dict, Any, Optional
from converters import get_voltage_mv, get_time_ms


def samples_to_hex(samples: List[int], sample_bytes: int = 1) -> str:
    """
    Convert samples list to hex string for compact transmission.
    
    Args:
        samples: List of sample values
        sample_bytes: Number of bytes per sample (1 or 2)
        
    Returns:
        Hex string representation of samples
    """
    if not samples:
        return ""
    if sample_bytes == 1:
        # [PL_AUDIT_WEB_B5] bytes(...).hex() is ~an order of magnitude faster than a
        # per-element f-string join on this per-frame hot path. Valid 8-bit samples
        # are 0..255; an out-of-range value raises here (caught upstream) rather than
        # silently emitting a wrong-width field (the old '{s:02x}' overflowed to 3+
        # chars for values >255, desyncing every following sample).
        return bytes(samples).hex()
    elif sample_bytes == 2:
        return ''.join(f'{s:04x}' for s in samples)
    else:
        return ''.join(f'{s:02x}' for s in samples)


def samples_from_hex(hex_str: str, sample_bytes: int = 1) -> List[int]:
    """
    Decode hex string back to samples list.
    
    Args:
        hex_str: Hex string representation of samples
        sample_bytes: Number of bytes per sample (1 or 2)
        
    Returns:
        List of sample values
    """
    if not hex_str:
        return []
    chars_per_sample = sample_bytes * 2
    return [int(hex_str[i:i+chars_per_sample], 16) 
            for i in range(0, len(hex_str), chars_per_sample)]


def samples_to_millivolts(samples: List[int], sample_bits: int, config: Dict[str, Any]) -> List[float]:
    """
    Convert raw ADC samples to millivolts.
    
    Args:
        samples: List of raw ADC sample values
        sample_bits: Number of bits per sample (typically 8 or 12)
        config: Device configuration containing voltage division settings
        
    Returns:
        List of voltage values in millivolts
    """
    if not samples:
        return []
    v_div_mv = get_voltage_mv(config)
    full_scale_mv = v_div_mv * 8.0
    max_code = (1 << sample_bits) - 1
    center = max_code / 2.0
    if center <= 0:
        return [0.0 for _ in samples]
    scale = full_scale_mv / 2.0
    return [((s - center) / center) * scale for s in samples]


def calculate_voltage_range(samples: List[int], 
                            sample_bits: int, 
                            config: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """
    Calculate min/max voltage from samples.
    
    Args:
        samples: List of raw ADC sample values
        sample_bits: Number of bits per sample
        config: Device configuration
        
    Returns:
        Dictionary with 'min_mv' and 'max_mv' keys
    """
    result: Dict[str, Optional[float]] = {"min_mv": None, "max_mv": None}
    
    if not samples:
        return result
    
    samples_mv = samples_to_millivolts(samples, sample_bits, config)
    if not samples_mv:
        return result
    
    try:
        result["min_mv"] = min(samples_mv)
        result["max_mv"] = max(samples_mv)
    except Exception:
        pass
    
    return result


def calculate_segments(samples: List[int], threshold: int) -> tuple[List[int], List[int]]:
    """
    Calculate positive and negative segments relative to threshold.
    
    A segment is a sequence of consecutive samples that are all above (positive)
    or all below (negative) the threshold value.
    
    Args:
        samples: List of raw sample values
        threshold: Threshold value (typically average of samples)
        
    Returns:
        Tuple of (positive_segments, negative_segments) where each is a list of segment lengths
    """
    if not samples:
        return [], []
    
    pos_segments: List[int] = []
    neg_segments: List[int] = []
    
    curr_segment_sign = True  # Start with positive
    curr_segment_len = 0
    
    for sample in samples:
        sign = (sample - threshold) > 0
        
        if curr_segment_sign == sign:
            curr_segment_len += 1
        else:
            if curr_segment_len > 0:
                if curr_segment_sign:
                    pos_segments.append(curr_segment_len)
                else:
                    neg_segments.append(curr_segment_len)
            
            curr_segment_sign = sign
            curr_segment_len = 1  # Start new segment with current sample
    
    # Add last segment
    if curr_segment_len > 0:
        if curr_segment_sign:
            pos_segments.append(curr_segment_len)
        else:
            neg_segments.append(curr_segment_len)
    
    return pos_segments, neg_segments


def calculate_average(values: List[int]) -> int:
    """Calculate integer average of a list of values."""
    if not values:
        return 0
    return sum(values) // len(values)


def filter_short_segments(segments: List[int], min_length: int) -> List[int]:
    """Filter out segments shorter than min_length."""
    return [seg for seg in segments if seg >= min_length]


def calculate_frequency_and_period(samples: List[int], 
                                   t_step_ms: float) -> Dict[str, Optional[float]]:
    """
    Calculate frequency and period using segment analysis algorithm.
    
    This algorithm:
    1. Calculates average value of samples
    2. Identifies positive and negative segments (sequences above/below average)
    3. Filters out short segments (noise)
    4. Calculates period from average segment lengths
    5. Derives frequency from period
    
    Args:
        samples: List of raw ADC sample values
        t_step_ms: Time per sample in milliseconds
        
    Returns:
        Dictionary with 'freq' (Hz), 'period' (seconds), and 'segments_count' keys
    """
    result: Dict[str, Optional[float]] = {"freq": None, "period": None, "segments_count": 0}
    
    if not samples or len(samples) == 0:
        return result
    
    # Calculate average (threshold)
    i_data_avg = sum(samples) // len(samples)
    
    # Calculate segments
    pos_segments, neg_segments = calculate_segments(samples, i_data_avg)
    
    if not pos_segments or not neg_segments:
        return result
    
    # Calculate average segment length for filtering
    avg_pos = calculate_average(pos_segments)
    avg_neg = calculate_average(neg_segments)
    avg_segment = (avg_pos + avg_neg) // 2
    
    # Filter short segments (noise removal)
    pos_segments = filter_short_segments(pos_segments, avg_segment)
    neg_segments = filter_short_segments(neg_segments, avg_segment)
    
    segments_count = len(pos_segments) + len(neg_segments)
    result["segments_count"] = segments_count

    # Need at least 3 segments for reliable frequency calculation
    if segments_count < 3:
        return result

    # [PL_AUDIT_WEB_B12] A full period is one positive run PLUS one negative run.
    # With a strongly asymmetric duty cycle the noise filter can drop *all* runs of
    # one sign while >=3 of the other survive; using 0 for the missing side then
    # yields a half-period and reports ~2x the true frequency. Require both sides.
    if not pos_segments or not neg_segments:
        return result

    # Calculate period
    avg_pos_filtered = calculate_average(pos_segments)
    avg_neg_filtered = calculate_average(neg_segments)

    t_period_ms = (avg_pos_filtered + avg_neg_filtered) * t_step_ms
    
    if t_period_ms > 0:
        result["freq"] = 1000.0 / t_period_ms  # Convert from ms to Hz
        result["period"] = t_period_ms / 1000.0  # Convert to seconds
    
    return result


def calculate_measurements(frame: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate measurements from frame metadata: frequency, period, Vpp, Vmax, Vmin, Vavg.
    
    Args:
        frame: Frame data containing samples and metadata
        config: Device configuration
        
    Returns:
        Dictionary with measurement values and units
    """
    if not frame:
        return {}

    sample_bits = int(frame.get("sample_bits") or 8)
    samples = list(frame.get("samples") or [])

    if not samples:
        return {}

    # Convert samples to voltages
    voltages_mv = samples_to_millivolts(samples, sample_bits, config)
    if not voltages_mv:
        return {}

    # Calculate voltage statistics directly from samples
    v_min_mv = min(voltages_mv)
    v_max_mv = max(voltages_mv)

    v_pp_mv = v_max_mv - v_min_mv
    v_avg_mv = sum(voltages_mv) / len(voltages_mv)

    # Frequency and period calculation using segment analysis (like in OscillData.java)
    freq = None
    period = None
    segments_count = 0
    try:
        # Calculate time step based on actual samples count, not configuration
        # This accounts for peak mode interpolation where samples are doubled
        h_divs = config.get("h_divs", 8)
        t_div_ms = get_time_ms(config)
        total_time_ms = t_div_ms * h_divs
        # Real time step between samples in the array
        t_step_ms = total_time_ms / max(1, len(samples))
        
        # Use samples for segment detection - works uniformly for all modes
        freq_period = calculate_frequency_and_period(samples, t_step_ms)
        freq = freq_period.get("freq")
        period = freq_period.get("period")
        segments_count = freq_period.get("segments_count", 0)
    except Exception:
        pass

    # Build measurements dictionary
    measurements: Dict[str, Any] = {}
    if freq is not None:
        measurements["freq"] = {"v": freq, "u": "Hz"}
    if period is not None:
        measurements["period"] = {"v": period, "u": "s"}
    measurements["v_pp"] = {"v": v_pp_mv / 1000.0, "u": "V"}
    measurements["v_max"] = {"v": v_max_mv / 1000.0, "u": "V"}
    measurements["v_min"] = {"v": v_min_mv / 1000.0, "u": "V"}
    measurements["v_avg"] = {"v": v_avg_mv / 1000.0, "u": "V"}

    return measurements
