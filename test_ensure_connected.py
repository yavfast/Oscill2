#!/usr/bin/env python3
"""
Test script for ensure_connected and renamed start/stop methods.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from web_oscill.device_service import DeviceService

def main():
    print("=== Testing ensure_connected and start/stop ===\n")
    
    service = DeviceService(buffer_size=64)
    
    try:
        # Test 1: ensure_connected when not connected (should auto-connect)
        print("Test 1: ensure_connected when not connected")
        status = service.get_status()
        print(f"  Initial status: {status.get('status')}")
        assert status['status'] == 'disconnected'
        
        result = service.ensure_connected()
        print(f"  After ensure_connected: {result.get('status')}")
        print(f"  Port: {result.get('port')}")
        assert result['status'] == 'ok'
        print("  ✓ Auto-connected successfully\n")
        
        # Test 2: ensure_connected when already connected (should return status)
        print("Test 2: ensure_connected when already connected")
        start = time.time()
        result = service.ensure_connected()
        elapsed = time.time() - start
        print(f"  Status: {result.get('status')}")
        print(f"  Took: {elapsed:.6f}s (should be fast)")
        assert result['status'] == 'ok'
        assert elapsed < 0.01  # Should be very fast
        print("  ✓ Returned status without reconnecting\n")
        
        # Test 3: stop() method
        print("Test 3: stop() method")
        result = service.stop()
        print(f"  Status: {result.get('status')}")
        status = service.get_status()
        print(f"  Is acquiring: {status.get('is_acquiring')}")
        assert result['status'] == 'ok'
        assert status['is_acquiring'] == False
        print("  ✓ Stopped successfully\n")
        
        # Test 4: start() method
        print("Test 4: start() method")
        result = service.start()
        print(f"  Status: {result.get('status')}")
        status = service.get_status()
        print(f"  Is acquiring: {status.get('is_acquiring')}")
        assert result['status'] == 'ok'
        assert status['is_acquiring'] == True
        print("  ✓ Started successfully\n")
        
        # Test 5: Backwards compatibility (start_acquisition/stop_acquisition still work)
        print("Test 5: Backwards compatibility")
        result = service.stop_acquisition()
        assert result['status'] == 'ok'
        result = service.start_acquisition()
        assert result['status'] == 'ok'
        print("  ✓ Old method names still work\n")
        
        # Test 6: Disconnect and ensure_connected again
        print("Test 6: Disconnect and ensure_connected again")
        service.disconnect()
        status = service.get_status()
        print(f"  After disconnect: {status.get('status')}")
        assert status['status'] == 'disconnected'
        
        result = service.ensure_connected()
        print(f"  After ensure_connected: {result.get('status')}")
        assert result['status'] == 'ok'
        print("  ✓ Reconnected successfully\n")
        
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
