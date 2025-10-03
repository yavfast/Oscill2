#!/bin/bash

# Test script for auto-adjust functionality
# Tests the scenario: set V/div to 200mV, auto should detect 20mV

BASE_URL="http://127.0.0.1:8000"

echo "=== Testing Auto-Adjust Functionality ==="
echo ""

# Get current status
echo "1. Getting current status..."
curl -s "$BASE_URL/api/status" | python3 -m json.tool
echo ""

# Set V/div to 200 mV (to make signal small)
echo "2. Setting V/div to 200 mV..."
curl -s -X POST "$BASE_URL/api/config" \
  -H "Content-Type: application/json" \
  -d '{"v_div": {"v": 200, "u": "mV"}}' | python3 -m json.tool
echo ""

sleep 1

# Run auto-adjust for v_div
echo "3. Running auto-adjust for v_div..."
curl -s -X POST "$BASE_URL/api/auto?types=v_div" | python3 -m json.tool
echo ""

# Get current status after auto-adjust
echo "4. Getting status after auto-adjust..."
curl -s "$BASE_URL/api/status" | python3 -m json.tool
echo ""

echo "=== Testing Time/div Auto-Adjust ==="
echo ""

# Set t_div to 10 ms
echo "5. Setting t_div to 10 ms..."
curl -s -X POST "$BASE_URL/api/config" \
  -H "Content-Type: application/json" \
  -d '{"t_div": {"v": 10, "u": "ms"}}' | python3 -m json.tool
echo ""

sleep 1

# Run auto-adjust for t_div
echo "6. Running auto-adjust for t_div..."
curl -s -X POST "$BASE_URL/api/auto?types=t_div" | python3 -m json.tool
echo ""

# Get current status after auto-adjust
echo "7. Getting status after auto-adjust..."
curl -s "$BASE_URL/api/status" | python3 -m json.tool
echo ""

echo "=== Test Complete ==="
