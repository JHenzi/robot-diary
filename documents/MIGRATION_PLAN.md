# Migration Plan: YouTube Live Stream Integration

## Overview

This document outlines the plan to migrate from the current Angelcam/Playwright approach to using YouTube Live streams as the video source.

## Current State

### What We Tried

1. **Windy Webcams API** ❌
   - **Issue**: Images were stale/outdated
   - **Status**: Removed from codebase

2. **Angelcam API** ❌
   - **Issue**: Public cameras endpoint requires OAuth2 integrator credentials
   - **Status**: Personal Access Tokens don't have `public_cameras_access` scope
   - **Result**: 403 Forbidden errors

3. **Playwright + Angelcam Iframe** ❌
   - **Issue**: Browser detection blocks video player ("Browser not supported")
   - **Attempted fixes**: User agent spoofing, webdriver property removal, realistic browser context
   - **Result**: Video player still doesn't load, no HLS requests generated

### Why YouTube Live?

- ✅ **Reliable**: YouTube's infrastructure is stable and well-maintained
- ✅ **Accessible**: Public streams don't require authentication
- ✅ **Real-time**: Live streams provide current content
- ✅ **Tools Available**: `yt-dlp` is mature and well-maintained
- ✅ **No Browser Detection**: Direct stream access, no browser automation needed

## Migration Steps

### Phase 1: Archive Current Code

1. **Create archive directory structure**:
   ```bash
   mkdir -p archive/angelcam-approach
   mkdir -p archive/windy-approach
   ```

2. **Archive Angelcam-related code**:
   - `src/camera/fetcher.py` (current Playwright implementation)
   - `src/camera/angelcam_client.py` (API client)
   - `analyze_cameras.py` (camera analysis script)
   - `inspect_webcam_page.py` (debugging script)
   - `test_angelcam_api.sh` (API testing script)
   - `webcam_example.py` (original example)
   - `AngelCamOpenAPISpec.json` (API specification)

3. **Archive Windy-related code** (if any remains):
   - Any Windy API client code
   - Windy-specific configuration

4. **Update `.gitignore`** to exclude archive directory from version control (optional)

### Phase 2: Implement YouTube Integration

1. **Add yt-dlp dependency**:
   ```bash
   pip install yt-dlp
   ```
   Add to `requirements.txt`

2. **Create new camera fetcher** (`src/camera/youtube_fetcher.py`):
   - Use `yt-dlp` to get stream URL
   - Extract frame using FFmpeg
   - Handle stream availability checks
   - Error handling for offline streams

3. **Update configuration**:
   - Add `YOUTUBE_STREAM_URL` to `.env.example`
   - Update `src/config.py` to read YouTube URL
   - Remove Angelcam/Windy configuration

4. **Update service**:
   - Modify `src/service.py` to use new YouTube fetcher
   - Update error handling
   - Update logging messages

### Phase 3: Testing & Validation

1. **Test frame extraction**:
   - Verify frames are captured correctly
   - Check image quality
   - Validate timestamps

2. **Test with service**:
   - Run full observation cycle
   - Verify Hugo post generation
   - Check memory updates

3. **Handle edge cases**:
   - Stream goes offline
   - Stream ends
   - Invalid stream URL
   - Network issues

### Phase 4: Cleanup

1. **Remove unused dependencies**:
   - Remove `playwright` from `requirements.txt` (if not needed elsewhere)
   - Remove `requests` if only used for Angelcam API

2. **Update documentation**:
   - ✅ README.md (already updated)
   - Update DEVELOPMENT_PLAN.md
   - Update any other relevant docs

3. **Clean up Docker**:
   - Remove Playwright/Chromium from Dockerfile
   - Keep FFmpeg (needed for frame extraction)
   - Add yt-dlp installation

## Implementation Details

### YouTube Fetcher Implementation

```python
# src/camera/youtube_fetcher.py (pseudo-code)

def fetch_latest_image(force_refresh: bool = False) -> Path:
    """
    Fetch a frame from YouTube live stream.
    
    1. Use yt-dlp to get stream URL
    2. Use FFmpeg to extract frame
    3. Save to images/ directory
    4. Return path to image
    """
    # Get stream URL with yt-dlp
    stream_url = get_youtube_stream_url(YOUTUBE_STREAM_URL)
    
    # Extract frame with FFmpeg
    frame_path = extract_frame_with_ffmpeg(stream_url)
    
    return frame_path
```

### yt-dlp Usage

```bash
# Get stream URL
yt-dlp -g "https://www.youtube.com/watch?v=VIDEO_ID"

# Or get best quality stream
yt-dlp -f "best" -g "https://www.youtube.com/watch?v=VIDEO_ID"
```

### FFmpeg Frame Extraction

```bash
# Extract single frame from stream
ffmpeg -i STREAM_URL -vframes 1 -update 1 output.jpg
```

## File Changes Summary

### Files to Archive
- `src/camera/fetcher.py` → `archive/angelcam-approach/fetcher.py`
- `src/camera/angelcam_client.py` → `archive/angelcam-approach/angelcam_client.py`
- `analyze_cameras.py` → `archive/angelcam-approach/analyze_cameras.py`
- `inspect_webcam_page.py` → `archive/angelcam-approach/inspect_webcam_page.py`
- `test_angelcam_api.sh` → `archive/angelcam-approach/test_angelcam_api.sh`
- `webcam_example.py` → `archive/angelcam-approach/webcam_example.py`
- `AngelCamOpenAPISpec.json` → `archive/angelcam-approach/AngelCamOpenAPISpec.json`

### Files to Create/Modify
- ✨ `src/camera/youtube_fetcher.py` (new)
- ✨ `src/camera/__init__.py` (update imports)
- ✨ `src/config.py` (add YOUTUBE_STREAM_URL)
- ✨ `src/service.py` (update to use YouTube fetcher)
- ✨ `requirements.txt` (add yt-dlp, remove playwright if not needed)
- ✨ `.env.example` (add YOUTUBE_STREAM_URL)
- ✨ `Dockerfile` (remove Playwright, add yt-dlp)

## Timeline

1. **Archive current code** (15 minutes)
2. **Implement YouTube fetcher** (1-2 hours)
3. **Update service and config** (30 minutes)
4. **Testing** (30 minutes)
5. **Documentation updates** (15 minutes)

**Total estimated time**: 2-3 hours

## Rollback Plan

If YouTube approach doesn't work:
- Archived code is preserved in `archive/` directory
- Can restore previous implementation
- Consider alternative: Direct HLS stream URLs if available

## Next Steps

1. ✅ Create this migration plan
2. ⏳ Archive current code
3. ⏳ Implement YouTube fetcher
4. ⏳ Test and validate
5. ⏳ Update documentation

