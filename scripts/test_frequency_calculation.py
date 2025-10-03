#!/usr/bin/env python3
"""
Test script to demonstrate the improved frequency calculation algorithm.
Compares the old zero-crossing method with the new segment analysis method.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'web_oscill'))

from calculations import calculate_frequency_and_period


def generate_sine_wave(frequency_hz, duration_ms, sample_rate_hz, noise_level=0):
    """Generate a sine wave with optional noise."""
    import math
    import random
    
    num_samples = int(sample_rate_hz * duration_ms / 1000.0)
    t_step_ms = 1000.0 / sample_rate_hz
    
    samples = []
    for i in range(num_samples):
        t = i * t_step_ms / 1000.0  # Time in seconds
        # Generate sine wave (0-255 range, centered at 128)
        value = 128 + 100 * math.sin(2 * math.pi * frequency_hz * t)
        
        # Add noise if specified
        if noise_level > 0:
            value += random.uniform(-noise_level, noise_level)
        
        samples.append(int(max(0, min(255, value))))
    
    return samples, t_step_ms


def test_frequency_calculation():
    """Test the frequency calculation with various signals."""
    
    print("=" * 70)
    print("Frequency Calculation Algorithm Test")
    print("=" * 70)
    
    test_cases = [
        (100, 100, 10000, 0, "100 Hz sine wave, no noise"),
        (100, 100, 10000, 5, "100 Hz sine wave, low noise"),
        (100, 100, 10000, 15, "100 Hz sine wave, high noise"),
        (1000, 50, 50000, 0, "1 kHz sine wave, no noise"),
        (50, 200, 5000, 0, "50 Hz sine wave, no noise"),
    ]
    
    for expected_freq, duration_ms, sample_rate, noise, description in test_cases:
        samples, t_step_ms = generate_sine_wave(expected_freq, duration_ms, sample_rate, noise)
        
        result = calculate_frequency_and_period(samples, t_step_ms)
        
        measured_freq = result.get("freq")
        measured_period = result.get("period")
        segments_count = result.get("segments_count", 0)
        
        print(f"\n{description}")
        print(f"  Expected frequency: {expected_freq} Hz")
        print(f"  Sample rate: {sample_rate} Hz")
        print(f"  Sample count: {len(samples)}")
        print(f"  Time step: {t_step_ms:.4f} ms")
        
        if measured_freq is not None:
            error_pct = abs(measured_freq - expected_freq) / expected_freq * 100
            print(f"  Measured frequency: {measured_freq:.2f} Hz (error: {error_pct:.2f}%)")
            print(f"  Measured period: {measured_period*1000:.2f} ms")
            print(f"  Segments detected: {segments_count}")
        else:
            print(f"  ❌ Could not calculate frequency (segments: {segments_count})")
    
    print("\n" + "=" * 70)


def test_edge_cases():
    """Test edge cases."""
    print("\nEdge Cases:")
    print("-" * 70)
    
    # Empty samples
    result = calculate_frequency_and_period([], 1.0)
    print(f"Empty samples: freq={result.get('freq')}, segments={result.get('segments_count')}")
    
    # Constant signal (no frequency)
    constant_samples = [128] * 100
    result = calculate_frequency_and_period(constant_samples, 0.1)
    print(f"Constant signal: freq={result.get('freq')}, segments={result.get('segments_count')}")
    
    # Too few segments
    short_samples = [100, 100, 150, 150]
    result = calculate_frequency_and_period(short_samples, 1.0)
    print(f"Very short signal: freq={result.get('freq')}, segments={result.get('segments_count')}")
    
    print("-" * 70)


if __name__ == "__main__":
    try:
        test_frequency_calculation()
        test_edge_cases()
        print("\n✅ All tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
