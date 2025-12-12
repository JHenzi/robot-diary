#!/bin/bash
# Test script for Angelcam API

# Load API key from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

if [ -z "$ANGEL_CAM_APIKEY" ]; then
    echo "ERROR: ANGEL_CAM_APIKEY not set in .env file"
    exit 1
fi

echo "Testing Angelcam API with PersonalAccessToken..."
echo "API Key (first 20 chars): ${ANGEL_CAM_APIKEY:0:20}..."
echo ""

# Test 1: Try the /me/ endpoint to verify token works first
echo "=== Test 1: Verify token with /me/ endpoint ==="
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
     -H "Authorization: PersonalAccessToken $ANGEL_CAM_APIKEY" \
     -H "Content-Type: application/json" \
     "https://api.angelcam.com/v1/me/")
echo "$response"
echo ""

# Test 2: Try with PersonalAccessToken format
echo "=== Test 2: PersonalAccessToken format (public-cameras) ==="
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
     -H "Authorization: PersonalAccessToken $ANGEL_CAM_APIKEY" \
     -H "Content-Type: application/json" \
     "https://api.angelcam.com/v1/public-cameras/?limit=10&online=1")
echo "$response"
echo ""

# Test 3: Try without online filter
echo "=== Test 3: Without online filter ==="
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
     -H "Authorization: PersonalAccessToken $ANGEL_CAM_APIKEY" \
     -H "Content-Type: application/json" \
     "https://api.angelcam.com/v1/public-cameras/?limit=10")
echo "$response"

