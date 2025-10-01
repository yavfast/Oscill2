#!/bin/bash
# Quick diagnostic script for hex encoding issues

echo "=== Hex Encoding Diagnostics ==="
echo ""

echo "1. Testing API response format:"
curl -s "http://localhost:8000/api/frames?format=hex&limit=1" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"  ✓ Format: {data.get('format')}\")
    frames = data.get('frames', [])
    print(f\"  ✓ Frames count: {len(frames)}\")
    if frames:
        frame = frames[0]
        print(f\"  ✓ Has samples_hex: {'samples_hex' in frame}\")
        print(f\"  ✓ Has samples: {'samples' in frame}\")
        if 'samples_hex' in frame:
            hex_len = len(frame['samples_hex'])
            print(f\"  ✓ Hex string length: {hex_len} chars ({hex_len//2} samples)\")
except Exception as e:
    print(f\"  ✗ Error: {e}\")
"
echo ""

echo "2. Testing array format (backward compatibility):"
curl -s "http://localhost:8000/api/frames?format=array&limit=1" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"  ✓ Format: {data.get('format')}\")
    frames = data.get('frames', [])
    if frames:
        frame = frames[0]
        print(f\"  ✓ Has samples: {'samples' in frame}\")
        if 'samples' in frame:
            print(f\"  ✓ Samples count: {len(frame['samples'])}\")
            print(f\"  ✓ First 5 samples: {frame['samples'][:5]}\")
except Exception as e:
    print(f\"  ✗ Error: {e}\")
"
echo ""

echo "3. Server status:"
if pgrep -f "uvicorn.*web_oscill.main" > /dev/null; then
    echo "  ✓ Server is running"
    PID=$(pgrep -f "uvicorn.*web_oscill.main")
    echo "  ✓ PID: $PID"
else
    echo "  ✗ Server is not running"
fi
echo ""

echo "4. Recent server errors:"
if [ -f "/hdd/PROJECTS/Oscill2/web_oscill.log" ]; then
    ERRORS=$(tail -50 /hdd/PROJECTS/Oscill2/web_oscill.log | grep -i "error\|exception\|traceback" | head -5)
    if [ -z "$ERRORS" ]; then
        echo "  ✓ No recent errors in log"
    else
        echo "  ⚠ Recent errors found:"
        echo "$ERRORS"
    fi
else
    echo "  ⚠ Log file not found"
fi
echo ""

echo "5. Browser cache busting:"
echo "  Main page: http://localhost:8000/"
echo "  Test page: http://localhost:8000/static/test_hex.html"
echo "  Clear browser cache: Ctrl+Shift+R or Ctrl+F5"
echo ""

echo "=== Diagnostics Complete ==="
