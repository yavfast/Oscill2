# Frames Endpoint Wait Feature

## Overview

Modified the `/api/frames` endpoint to intelligently wait for new data when acquisition is running, instead of immediately returning an empty frame list.

## Implementation

### Changes Made

**File: `web_oscill/main.py`**

1. **Added `time` import** for sleep functionality
2. **Modified `/api/frames` endpoint** to wait up to 5 seconds for frames when:
   - The frame buffer would return empty results
   - Data acquisition is currently running (`service._is_acquiring == True`)

### How It Works

```python
# Check if we would return empty frames
if not frames and service._is_acquiring:
    # Wait up to 5 seconds for new frames
    max_wait_time = 5.0
    wait_interval = 0.05  # Check every 50ms
    elapsed = 0.0
    
    while elapsed < max_wait_time and service._is_acquiring:
        time.sleep(wait_interval)
        elapsed += wait_interval
        
        # Re-check for new frames
        data = service.get_frames(since=since, limit=limit)
        frames = data.get("frames", [])
        
        if frames:
            break  # Exit early if frames arrive
```

## Benefits

### 1. **Reduced Empty Responses**
- Frontend no longer receives empty frame lists during active acquisition
- Improves data continuity for real-time display

### 2. **Better Resource Utilization**
- Reduces unnecessary HTTP request/response cycles
- Frontend doesn't need to poll as aggressively

### 3. **Improved UX**
- More responsive data updates
- Smoother graph rendering with fewer gaps

### 4. **Smart Waiting**
- Only waits when acquisition is active (`_is_acquiring`)
- Returns immediately if disconnected or acquisition stopped
- Exits early when frames arrive (doesn't wait full 5 seconds)

## Configuration

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `max_wait_time` | 5.0 seconds | Maximum time to wait for frames |
| `wait_interval` | 0.05 seconds (50ms) | Polling interval for new frames |

## API Behavior

### Before Change
```
GET /api/frames?since=100
→ Returns immediately, possibly empty: {"frames": []}
```

### After Change
```
GET /api/frames?since=100
→ If acquiring and empty:
  - Waits up to 5s checking every 50ms
  - Returns as soon as frames available
  - Or returns empty after 5s timeout
```

## Edge Cases Handled

1. **Acquisition Stopped During Wait**
   - Loop checks `service._is_acquiring` on each iteration
   - Exits immediately if acquisition stops

2. **Device Disconnected**
   - Initial check returns `{"status": "disconnected"}` immediately
   - No waiting occurs

3. **Frames Arrive Early**
   - Loop breaks as soon as frames are detected
   - Minimizes response latency

4. **No Frames After Timeout**
   - Returns empty list after 5 seconds
   - Client can retry or handle gracefully

## Performance Impact

- **Best Case**: Frames arrive within 50ms → Response in ~50ms
- **Worst Case**: No frames for 5s → Response in ~5s (vs immediate before)
- **Typical Case**: Frames arrive within 100-500ms → Response matches actual data rate

## Testing Recommendations

1. **Normal Operation**
   - Start acquisition
   - Request frames with `since` parameter
   - Verify responses include data within reasonable time

2. **Empty Buffer**
   - Stop acquisition
   - Request frames
   - Verify immediate empty response

3. **Mid-Wait Disconnection**
   - Start acquisition
   - Request frames (triggering wait)
   - Disconnect device during wait
   - Verify loop exits promptly

4. **High-Frequency Requests**
   - Multiple concurrent requests
   - Verify no deadlocks or excessive delays

## Future Enhancements

Consider adding:
- Configurable wait timeout via query parameter: `/api/frames?timeout=10`
- WebSocket endpoint for push-based frame delivery
- Event-driven notification when frames arrive (instead of polling)

## Related Files

- `web_oscill/main.py` - Endpoint implementation
- `web_oscill/device_service.py` - Frame buffer and acquisition state
- `static/js/modules/api.js` - Frontend API client

## Version Info

- **Date**: 2025-01-02
- **Feature**: Smart frame waiting
- **Timeout**: 5 seconds
- **Poll Interval**: 50ms
