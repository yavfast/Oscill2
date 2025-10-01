#!/usr/bin/env python3
"""
Test script to compare hex vs array encoding for samples.
Demonstrates size savings and performance improvements.
"""

import json
import time
from typing import List

def samples_to_hex(samples: List[int], sample_bytes: int = 1) -> str:
    """Convert samples list to hex string."""
    if sample_bytes == 1:
        return ''.join(f'{s:02x}' for s in samples)
    elif sample_bytes == 2:
        return ''.join(f'{s:04x}' for s in samples)
    return ''.join(f'{s:02x}' for s in samples)

def hex_to_samples(hex_str: str, sample_bytes: int = 1) -> List[int]:
    """Convert hex string to samples list."""
    chars_per_sample = sample_bytes * 2
    return [int(hex_str[i:i+chars_per_sample], 16) 
            for i in range(0, len(hex_str), chars_per_sample)]

def test_encoding(sample_count: int = 320):
    """Test encoding performance and size."""
    # Generate sample data (simulate oscilloscope readings)
    import random
    samples = [random.randint(0, 255) for _ in range(sample_count)]
    
    print(f"\n{'='*60}")
    print(f"Testing with {sample_count} samples")
    print(f"{'='*60}\n")
    
    # Test JSON array format
    print("📊 JSON Array Format:")
    array_data = {"samples": samples}
    array_json = json.dumps(array_data)
    array_size = len(array_json)
    
    start = time.perf_counter()
    for _ in range(1000):
        json.dumps(array_data)
    array_serialize_time = (time.perf_counter() - start) / 1000 * 1000  # ms
    
    start = time.perf_counter()
    for _ in range(1000):
        json.loads(array_json)
    array_parse_time = (time.perf_counter() - start) / 1000 * 1000  # ms
    
    print(f"  Size: {array_size:,} bytes")
    print(f"  Serialize: {array_serialize_time:.3f} ms")
    print(f"  Parse: {array_parse_time:.3f} ms")
    print(f"  Sample: {array_json[:80]}...")
    
    # Test hex format
    print("\n🔢 Hex String Format:")
    hex_str = samples_to_hex(samples, 1)
    hex_data = {"samples_hex": hex_str}
    hex_json = json.dumps(hex_data)
    hex_size = len(hex_json)
    
    start = time.perf_counter()
    for _ in range(1000):
        json.dumps(hex_data)
    hex_serialize_time = (time.perf_counter() - start) / 1000 * 1000  # ms
    
    start = time.perf_counter()
    for _ in range(1000):
        data = json.loads(hex_json)
        hex_to_samples(data["samples_hex"], 1)
    hex_parse_time = (time.perf_counter() - start) / 1000 * 1000  # ms
    
    print(f"  Size: {hex_size:,} bytes")
    print(f"  Serialize: {hex_serialize_time:.3f} ms")
    print(f"  Parse: {hex_parse_time:.3f} ms")
    print(f"  Sample: {hex_json[:80]}...")
    
    # Calculate improvements
    print(f"\n✨ Improvements:")
    size_reduction = array_size - hex_size
    size_percent = (size_reduction / array_size) * 100
    serialize_speedup = array_serialize_time / hex_serialize_time
    parse_speedup = array_parse_time / hex_parse_time
    
    print(f"  Size reduction: {size_reduction:,} bytes ({size_percent:.1f}% smaller)")
    print(f"  Serialize speedup: {serialize_speedup:.2f}x faster")
    print(f"  Parse speedup: {parse_speedup:.2f}x faster")
    
    # Verify correctness
    decoded = hex_to_samples(hex_str, 1)
    if decoded == samples:
        print(f"  ✅ Encoding/decoding verified correct")
    else:
        print(f"  ❌ Encoding/decoding mismatch!")
    
    # Estimate real-world impact
    print(f"\n🌍 Real-world Impact:")
    frames_per_sec = 10  # 10 Hz polling
    hours = 1
    total_frames = frames_per_sec * 3600 * hours
    
    array_total = (array_size * total_frames) / (1024 * 1024)
    hex_total = (hex_size * total_frames) / (1024 * 1024)
    savings_mb = array_total - hex_total
    
    print(f"  In {hours} hour(s) at {frames_per_sec} Hz:")
    print(f"    Array format: {array_total:.1f} MB")
    print(f"    Hex format: {hex_total:.1f} MB")
    print(f"    Savings: {savings_mb:.1f} MB")
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    print("\n🧪 Hex Encoding Performance Test")
    print("Testing oscilloscope sample data encoding\n")
    
    # Test with different sample counts
    for count in [64, 128, 320, 640]:
        test_encoding(count)
    
    print("✅ All tests completed!\n")
