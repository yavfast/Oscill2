#!/usr/bin/env python3
"""
Test script for DeviceService with executor pool and cached config.
"""
import time
import sys
import os

# Add web_oscill to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'web_oscill'))

from web_oscill.device_service import DeviceService

def main():
    print("=== Testing DeviceService with Executor Pool ===\n")
    
    service = DeviceService(buffer_size=64)
    
    try:
        # Test 1: Get status when disconnected
        print("Test 1: Get status when disconnected")
        status = service.get_status()
        print(f"  Status: {status.get('status')}")
        print(f"  Connected: {status.get('is_connected')}")
        assert status['status'] == 'disconnected'
        print("  ✓ Passed\n")
        
        # Test 2: Connect to device
        print("Test 2: Connect to device")
        start = time.time()
        result = service.connect()
        elapsed = time.time() - start
        print(f"  Connect took {elapsed:.3f}s")
        print(f"  Status: {result.get('status')}")
        print(f"  Port: {result.get('port')}")
        assert result['status'] == 'ok'
        print("  ✓ Passed\n")
        
        # Test 3: Get status (should use cached config, be fast)
        print("Test 3: Get status (should be fast with cached config)")
        start = time.time()
        status = service.get_status()
        elapsed = time.time() - start
        print(f"  get_status took {elapsed:.6f}s (should be < 0.001s)")
        print(f"  Status: {status.get('status')}")
        print(f"  Config ID: {status.get('cfg_id')}")
        print(f"  Connected: {status.get('is_connected')}")
        assert status['status'] == 'ok'
        assert elapsed < 0.01  # Should be very fast
        print("  ✓ Passed\n")
        
        # Test 4: Multiple rapid status calls
        print("Test 4: Multiple rapid get_status calls")
        start = time.time()
        for i in range(100):
            status = service.get_status()
            assert status['status'] == 'ok'
        elapsed = time.time() - start
        print(f"  100 get_status calls took {elapsed:.3f}s")
        print(f"  Average: {elapsed/100*1000:.3f}ms per call")
        assert elapsed < 0.5  # 100 calls should take less than 0.5s
        print("  ✓ Passed\n")
        
        # Test 5: Wait for some frames
        print("Test 5: Wait for frames to be acquired")
        time.sleep(2)
        frame = service.get_latest_frame()
        if frame:
            print(f"  Got frame with {len(frame.get('samples', []))} samples")
        assert frame is not None
        print("  ✓ Passed\n")
        
        # Test 6: Apply config (goes through executor)
        print("Test 6: Apply config change")
        old_cfg_id = status['cfg_id']
        start = time.time()
        result, warnings = service.apply_config({
            'v_div': {'v': 500, 'u': 'mV'}
        })
        elapsed = time.time() - start
        print(f"  apply_config took {elapsed:.3f}s")
        print(f"  New config ID: {result.get('cfg_id')}")
        assert result['cfg_id'] > old_cfg_id
        print("  ✓ Passed\n")
        
        # Test 7: Get status again (should have new config)
        print("Test 7: Get status after config change")
        start = time.time()
        status = service.get_status()
        elapsed = time.time() - start
        print(f"  get_status took {elapsed:.6f}s")
        print(f"  Config ID: {status.get('cfg_id')}")
        print(f"  V_div: {status['config'].get('v_div')}")
        assert elapsed < 0.01
        print("  ✓ Passed\n")
        
        # Test 8: Disconnect
        print("Test 8: Disconnect")
        start = time.time()
        result = service.disconnect()
        elapsed = time.time() - start
        print(f"  Disconnect took {elapsed:.3f}s")
        print(f"  Status: {result.get('status')}")
        assert result['status'] == 'ok'
        print("  ✓ Passed\n")
        
        # Test 9: Get status after disconnect
        print("Test 9: Get status after disconnect")
        status = service.get_status()
        print(f"  Status: {status.get('status')}")
        print(f"  Connected: {status.get('is_connected')}")
        assert status['status'] == 'disconnected'
        print("  ✓ Passed\n")
        
        print("=== All tests passed! ===")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        service.shutdown()
        print("\nService shut down.")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
