# Angelcam Approach Archive

This directory contains the code from attempts to use Angelcam as the video source.

## What Was Tried

1. **Angelcam API**: Attempted to use the public cameras API endpoint
   - Required OAuth2 integrator credentials
   - Personal Access Tokens don't have `public_cameras_access` scope
   - Result: 403 Forbidden errors

2. **Playwright + Iframe**: Attempted to extract HLS URL from embedded iframe
   - Browser detection blocked video player ("Browser not supported")
   - Tried user agent spoofing, webdriver property removal
   - Result: Video player wouldn't load, no HLS requests generated

## Files

- `fetcher.py`: Main Playwright-based fetcher implementation
- `angelcam_client.py`: API client for Angelcam (unused due to permissions)
- `analyze_cameras.py`: Script to analyze and select cameras
- `inspect_webcam_page.py`: Debugging script to inspect page structure
- `test_angelcam_api.sh`: API testing script
- `webcam_example.py`: Original example code
- `AngelCamOpenAPISpec.json`: API specification
