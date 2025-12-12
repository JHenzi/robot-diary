#!/bin/bash
# Script to archive old camera-related code before migration to YouTube

set -e

echo "📦 Archiving old camera implementation code..."

# Create archive directories
mkdir -p archive/angelcam-approach
mkdir -p archive/windy-approach

# Archive Angelcam-related files
echo "Archiving Angelcam approach..."
if [ -f "src/camera/fetcher.py" ]; then
    cp src/camera/fetcher.py archive/angelcam-approach/fetcher.py
    echo "  ✅ Archived src/camera/fetcher.py"
fi

if [ -f "src/camera/angelcam_client.py" ]; then
    cp src/camera/angelcam_client.py archive/angelcam-approach/angelcam_client.py
    echo "  ✅ Archived src/camera/angelcam_client.py"
fi

if [ -f "analyze_cameras.py" ]; then
    cp analyze_cameras.py archive/angelcam-approach/
    echo "  ✅ Archived analyze_cameras.py"
fi

if [ -f "inspect_webcam_page.py" ]; then
    cp inspect_webcam_page.py archive/angelcam-approach/
    echo "  ✅ Archived inspect_webcam_page.py"
fi

if [ -f "test_angelcam_api.sh" ]; then
    cp test_angelcam_api.sh archive/angelcam-approach/
    echo "  ✅ Archived test_angelcam_api.sh"
fi

if [ -f "webcam_example.py" ]; then
    cp webcam_example.py archive/angelcam-approach/
    echo "  ✅ Archived webcam_example.py"
fi

if [ -f "AngelCamOpenAPISpec.json" ]; then
    cp AngelCamOpenAPISpec.json archive/angelcam-approach/
    echo "  ✅ Archived AngelCamOpenAPISpec.json"
fi

if [ -f "page_inspection_requests.json" ]; then
    cp page_inspection_requests.json archive/angelcam-approach/
    echo "  ✅ Archived page_inspection_requests.json"
fi

# Create README in archive
cat > archive/angelcam-approach/README.md << 'EOF'
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
EOF

echo ""
echo "✅ Archive complete!"
echo "   Files archived to: archive/angelcam-approach/"
echo ""
echo "Next steps:"
echo "  1. Review archived files"
echo "  2. Implement YouTube fetcher (see MIGRATION_PLAN.md)"
echo "  3. Update service to use new fetcher"

