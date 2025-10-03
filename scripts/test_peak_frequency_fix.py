#!/usr/bin/env python3
"""
Test to verify that Peak mode frequency calculation is correct.
In Peak mode, we should NOT double the frequency.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'web_oscill'))

from calculations import calculate_measurements


def create_test_frame_normal(frequency_hz=100, sample_rate_hz=10000, duration_ms=100):
    """Create a test frame in normal mode."""
    import math
    
    num_samples = int(sample_rate_hz * duration_ms / 1000.0)
    samples = []
    
    for i in range(num_samples):
        t = i / sample_rate_hz
        # Sine wave centered at 128, amplitude 100
        value = 128 + 100 * math.sin(2 * math.pi * frequency_hz * t)
        samples.append(int(max(0, min(255, value))))
    
    return {
        "samples": samples,
        "sample_bits": 8,
    }


def create_test_frame_peak(frequency_hz=100, sample_rate_hz=10000, duration_ms=100):
    """Create a test frame in peak mode with peak_min and peak_max."""
    import math
    
    num_samples = int(sample_rate_hz * duration_ms / 1000.0)
    peak_min = []
    peak_max = []
    
    for i in range(num_samples):
        t = i / sample_rate_hz
        # Sine wave centered at 128, amplitude 100
        value = 128 + 100 * math.sin(2 * math.pi * frequency_hz * t)
        
        # Simulate peak detection: min is slightly lower, max is slightly higher
        min_val = int(max(0, min(255, value - 10)))
        max_val = int(max(0, min(255, value + 10)))
        
        peak_min.append(min_val)
        peak_max.append(max_val)
    
    # In peak mode, samples array is optional or reconstructed
    samples = [(lo + hi) // 2 for lo, hi in zip(peak_min, peak_max)]
    
    return {
        "samples": samples,
        "samples_peak_min": peak_min,
        "samples_peak_max": peak_max,
        "sample_bits": 8,
    }


def create_test_config(sample_rate_hz=10000):
    """Create a test config."""
    samples_per_div = 32
    # Calculate t_div to match sample rate
    # sample_rate = samples_per_div / t_div_ms * 1000
    # t_div_ms = samples_per_div / sample_rate * 1000
    t_div_ms = samples_per_div / sample_rate_hz * 1000
    
    return {
        "v_div": {"v": 500, "u": "mV"},  # 500 mV per division
        "t_div": {"v": t_div_ms, "u": "ms"},
        "samples_per_div": samples_per_div,
    }


def test_frequency_modes():
    """Test frequency calculation in different modes."""
    print("=" * 70)
    print("Peak Mode Frequency Fix Test")
    print("=" * 70)
    
    expected_freq = 100  # Hz
    sample_rate = 10000  # Hz
    
    # Test 1: Normal mode
    print("\n1. Normal Mode (no peak data):")
    frame_normal = create_test_frame_normal(expected_freq, sample_rate)
    config = create_test_config(sample_rate)
    
    measurements = calculate_measurements(frame_normal, config)
    freq_normal = measurements.get("freq", {}).get("v")
    
    if freq_normal:
        error_pct = abs(freq_normal - expected_freq) / expected_freq * 100
        print(f"   Expected: {expected_freq} Hz")
        print(f"   Measured: {freq_normal:.2f} Hz")
        print(f"   Error: {error_pct:.2f}%")
        print(f"   ✅ PASS" if error_pct < 5 else f"   ❌ FAIL")
    else:
        print("   ❌ FAIL - No frequency calculated")
    
    # Test 2: Peak mode
    print("\n2. Peak Mode (with peak_min and peak_max):")
    frame_peak = create_test_frame_peak(expected_freq, sample_rate)
    
    measurements = calculate_measurements(frame_peak, config)
    freq_peak = measurements.get("freq", {}).get("v")
    
    if freq_peak:
        error_pct = abs(freq_peak - expected_freq) / expected_freq * 100
        print(f"   Expected: {expected_freq} Hz")
        print(f"   Measured: {freq_peak:.2f} Hz")
        print(f"   Error: {error_pct:.2f}%")
        
        # Check if frequency is NOT doubled
        is_doubled = abs(freq_peak - expected_freq * 2) < abs(freq_peak - expected_freq)
        if is_doubled:
            print(f"   ❌ FAIL - Frequency is doubled!")
        else:
            print(f"   ✅ PASS" if error_pct < 5 else f"   ⚠️  ACCEPTABLE (error < 10%)" if error_pct < 10 else f"   ❌ FAIL")
    else:
        print("   ❌ FAIL - No frequency calculated")
    
    # Test 3: Verify they are close
    print("\n3. Comparison:")
    if freq_normal and freq_peak:
        diff_pct = abs(freq_normal - freq_peak) / expected_freq * 100
        print(f"   Normal mode:  {freq_normal:.2f} Hz")
        print(f"   Peak mode:    {freq_peak:.2f} Hz")
        print(f"   Difference:   {diff_pct:.2f}%")
        print(f"   ✅ Both modes give similar results" if diff_pct < 5 else f"   ❌ Results differ significantly")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        test_frequency_modes()
        print("\n✅ Test completed!")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
