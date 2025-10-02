# DeviceService Architecture with Executor Pool and Config Cache

## Before Optimization

```
Web Request → DeviceService.get_status()
                    ↓
              Device Lock (blocks)
                    ↓
           Query Device Hardware ← SLOW (~0.1-0.5s)
                    ↓
              Return Config
```

**Problem**: Every status request blocks and queries hardware

## After Optimization

```
┌─────────────────────────────────────────────────────────┐
│                    DeviceService                         │
│                                                          │
│  ┌──────────────────┐        ┌──────────────────┐      │
│  │  Cached Config   │◄───────│   Config Lock    │      │
│  │  _cached_config  │        │  (thread-safe)   │      │
│  └──────────────────┘        └──────────────────┘      │
│         ▲                                               │
│         │ update                                        │
│         │                                               │
│  ┌──────┴───────────────────────────────────────┐      │
│  │     Single-Thread Executor Pool              │      │
│  │     (max_workers=1, timeout=5s)              │      │
│  │                                               │      │
│  │  ┌─────────────────────────────────────┐     │      │
│  │  │  Device Command Queue               │     │      │
│  │  │  - connect()                        │     │      │
│  │  │  - disconnect()                     │     │      │
│  │  │  - apply_config()                   │     │      │
│  │  └─────────────────────────────────────┘     │      │
│  └──────────────┬────────────────────────────────┘      │
│                 │                                        │
│                 ▼                                        │
│         ┌──────────────┐                                │
│         │ Device Lock  │                                │
│         └──────┬───────┘                                │
│                │                                         │
│                ▼                                         │
│        ┌──────────────┐                                 │
│        │ USB Hardware │                                 │
│        └──────────────┘                                 │
│                ▲                                         │
│                │                                         │
│         ┌──────┴───────┐                                │
│         │  Acq Thread  │ (background, updates cache)    │
│         └──────────────┘                                │
└─────────────────────────────────────────────────────────┘

Web Requests:

Fast Path (no device access):
  get_status() → read _cached_config → return (<0.001s)
  
Slow Path (through executor):
  connect()      → executor.submit() → device operation (timeout 5s)
  disconnect()   → executor.submit() → device operation (timeout 5s)
  apply_config() → executor.submit() → device operation + cache update (timeout 5s)
```

## Key Components

### 1. Config Cache
- **_cached_config**: In-memory dict with last known config
- **_config_lock**: Threading lock for safe access
- **Updated by**: connect(), apply_config(), _acq_loop()
- **Read by**: get_status() (no blocking!)

### 2. Executor Pool
- **Single-threaded**: Serializes all device commands
- **Timeout**: 5 seconds per operation
- **Benefits**: 
  - Prevents command collisions
  - Graceful timeout handling
  - Clean async execution

### 3. Request Flow

#### High-frequency status requests (UI polling):
```
Client → /api/status
         ↓
    get_status() (immediate, no locking)
         ↓
    Read _cached_config
         ↓
    Return cached data
         ↓
    Client (< 1ms response time)
```

#### Config changes:
```
Client → /api/config
         ↓
    apply_config(changes)
         ↓
    Submit to executor queue
         ↓
    Wait for result (max 5s)
         ↓
    Device operation under lock
         ↓
    Update _cached_config
         ↓
    Return new config
         ↓
    Client
```

## Performance Comparison

| Operation         | Before      | After       | Improvement |
|-------------------|-------------|-------------|-------------|
| get_status()      | 100-500ms   | <1ms        | 100-500x    |
| 100x get_status() | 10-50s      | <0.1s       | 100-500x    |
| apply_config()    | 100-500ms   | 100-500ms   | Same*       |
| connect()         | 1-3s        | 1-3s        | Same*       |

*But now with timeout protection

## Thread Safety

All operations are thread-safe:
- Device access: Serialized by executor + dev_lock
- Config cache: Protected by _config_lock
- Frame buffer: Protected by _frames_lock
- Acquisition: Background thread with proper locking
