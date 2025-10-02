#!/bin/bash
# Test new API endpoints

BASE_URL="http://localhost:8000"

echo "=== Testing New API Endpoints ==="
echo

echo "1. Testing POST /api/connect (auto-connect)"
curl -X POST "$BASE_URL/api/connect" -H "Content-Type: application/json" -d '{}' 
echo -e "\n"

echo "2. Testing GET /api/status"
curl -X GET "$BASE_URL/api/status"
echo -e "\n"

echo "3. Testing POST /api/stop"
curl -X POST "$BASE_URL/api/stop"
echo -e "\n"

echo "4. Testing POST /api/start"
curl -X POST "$BASE_URL/api/start"
echo -e "\n"

echo "5. Testing POST /api/connect with specific port"
curl -X POST "$BASE_URL/api/connect" -H "Content-Type: application/json" -d '{"port": "/dev/ttyUSB0", "baud": 115200}'
echo -e "\n"

echo "=== Tests complete ==="
