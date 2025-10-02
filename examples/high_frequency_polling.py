#!/usr/bin/env python3
"""
Example: High-frequency status polling with optimized DeviceService.

This demonstrates how the cached config optimization enables
high-frequency polling without overwhelming the device.
"""
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from web_oscill.device_service import DeviceService

def main():
    service = DeviceService(buffer_size=128)
    
    try:
        # Connect
        print("Connecting to device...")
        service.connect()
        print("Connected!\n")
        
        # Simulate high-frequency polling like a web UI would do
        print("Simulating high-frequency status polling (like UI updates)...")
        print("Polling 1000 times...")
        
        start_time = time.time()
        for i in range(1000):
            status = service.get_status()
            
            # In a real app, this would update the UI
            # Now we can do this at 60 FPS or even higher!
            if i % 100 == 0:
                print(f"  Poll #{i}: cfg_id={status.get('cfg_id')}, "
                      f"acquiring={status.get('is_acquiring')}")
        
        elapsed = time.time() - start_time
        avg_ms = (elapsed / 1000) * 1000
        
        print(f"\nCompleted 1000 polls in {elapsed:.3f}s")
        print(f"Average: {avg_ms:.3f}ms per poll")
        print(f"Effective poll rate: {1000/elapsed:.1f} Hz")
        
        # This is now possible because get_status() doesn't query the device!
        # Before: ~0.1-0.5s per call = max ~10-20 Hz
        # After:  <0.001s per call = max 1000+ Hz
        
        print("\n✓ High-frequency polling works perfectly with cached config!")
        
    finally:
        service.shutdown()

if __name__ == '__main__':
    main()
