#!/usr/bin/env python3
"""
MANUAL HARDWARE TEST — frequency calculation across SW modes on a real device.

This is NOT a hardware-free unit test. It requires:
  * a live web_oscill server running at BASE_URL, and
  * a physical Oscill device connected with a signal applied.

It also drives an endpoint (/api/acquire/single) that is part of the manual
acquisition flow. Because none of that is available in CI / on a bare checkout,
running this unguarded produced a permanent FALSE FAILURE (item PL_AUDIT_WEB_09).

Behaviour now: by default the script SKIPS with an explanatory message and
exits 0. To actually run it against real hardware, set OSCILL_HW_TEST=1:

    OSCILL_HW_TEST=1 python3 scripts/test_real_device_frequency.py
"""

import os
import sys
import time

BASE_URL = "http://localhost:8000"


def _skip(reason):
    print("=" * 70)
    print("SKIP: test_real_device_frequency (manual hardware test)")
    print("=" * 70)
    print(f"  Reason: {reason}")
    print("  Set OSCILL_HW_TEST=1 and start the server with a connected device to run it.")
    sys.exit(0)


if os.environ.get("OSCILL_HW_TEST") != "1":
    _skip("OSCILL_HW_TEST != 1 (default: no live server/device assumed)")

try:
    import requests  # noqa: E402  (only needed when actually running against hardware)
except ImportError:
    _skip("'requests' is not installed")

# Fail fast (still exit 0) if the server is unreachable, so this never becomes a
# false failure even when explicitly opted in without a running server.
try:
    requests.get(f"{BASE_URL}/api/status", timeout=3)
except Exception as exc:  # noqa: BLE001
    _skip(f"server at {BASE_URL} is not reachable ({exc})")

def test_frequency_in_modes():
    """Test frequency calculation in different SW modes."""
    print("=" * 70)
    print("Real Device Frequency Test")
    print("=" * 70)
    
    # Check connection
    print("\n1. Checking device status...")
    try:
        resp = requests.get(f"{BASE_URL}/api/status", timeout=5)
        status = resp.json()
        
        if status.get("status") != "ok":
            print("   ⚠️  Device not connected. Attempting to connect...")
            resp = requests.post(f"{BASE_URL}/api/connect", json={}, timeout=10)
            print(f"   Connect result: {resp.json()}")
            time.sleep(2)
            
            # Check status again
            resp = requests.get(f"{BASE_URL}/api/status", timeout=5)
            status = resp.json()
        
        if status.get("status") == "ok":
            print("   ✅ Device connected")
            config = status.get("config", {})
            print(f"   Current sw_mode: {config.get('sw_mode', 'unknown')}")
        else:
            print("   ❌ Device not available")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Test modes
    modes_to_test = [
        ("NORMAL", "Normal mode"),
        ("AVG", "Average mode"),
        ("PEAK", "Peak mode"),
    ]
    
    results = {}
    
    for mode_key, mode_desc in modes_to_test:
        print(f"\n2. Testing {mode_desc} ({mode_key})...")
        
        try:
            # Set mode
            print(f"   Setting sw_mode to {mode_key}...")
            resp = requests.post(f"{BASE_URL}/api/config", 
                               json={"sw_mode": mode_key}, 
                               timeout=10)
            
            if resp.status_code != 200:
                print(f"   ❌ Failed to set mode: {resp.text}")
                continue
            
            print(f"   ✅ Mode set to {mode_key}")
            time.sleep(1)
            
            # Get measurements
            print(f"   Acquiring data...")
            resp = requests.get(f"{BASE_URL}/api/acquire/single", timeout=10)
            
            if resp.status_code != 200:
                print(f"   ❌ Failed to acquire: {resp.text}")
                continue
            
            data = resp.json()
            measurements = data.get("measurements", {})
            freq_data = measurements.get("freq")
            
            if freq_data:
                freq = freq_data.get("v")
                results[mode_key] = freq
                print(f"   ✅ Frequency: {freq:.2f} Hz")
            else:
                print(f"   ⚠️  No frequency data")
                results[mode_key] = None
            
            # Show raw data info
            samples = data.get("samples", [])
            peak_min = data.get("samples_peak_min", [])
            peak_max = data.get("samples_peak_max", [])
            print(f"   Samples: {len(samples)}, Peak min: {len(peak_min)}, Peak max: {len(peak_max)}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Compare results
    print("\n3. Comparison:")
    print("-" * 70)
    
    for mode_key, mode_desc in modes_to_test:
        freq = results.get(mode_key)
        if freq is not None:
            print(f"   {mode_desc:20s}: {freq:8.2f} Hz")
        else:
            print(f"   {mode_desc:20s}: No data")
    
    # Check if PEAK is doubled
    if results.get("PEAK") and results.get("NORMAL"):
        peak_freq = results["PEAK"]
        normal_freq = results["NORMAL"]
        ratio = peak_freq / normal_freq
        
        print(f"\n   Ratio (PEAK/NORMAL): {ratio:.2f}x")
        
        if abs(ratio - 2.0) < 0.1:
            print(f"   ❌ PEAK mode shows DOUBLED frequency!")
        elif abs(ratio - 1.0) < 0.1:
            print(f"   ✅ PEAK mode shows CORRECT frequency!")
        else:
            print(f"   ⚠️  Unexpected ratio")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        test_frequency_in_modes()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
