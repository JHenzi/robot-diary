"""Inspect the Troy, Ohio webcam page to understand how to get the stream URL."""
import asyncio
import json
from playwright.async_api import async_playwright

WEBCAM_URL = "https://troyohio.gov/542/Live-Downtown-Webcams"
M3U8_IDENTIFIER = "playlist.m3u8"


async def inspect_page():
    """Inspect the webcam page to find how the stream URL is accessed."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False so we can see what's happening
        page = await browser.new_page()
        
        # Track all network requests
        all_requests = []
        all_responses = []
        
        def handle_request(request):
            all_requests.append({
                'url': request.url,
                'method': request.method,
                'resource_type': request.resource_type
            })
            if M3U8_IDENTIFIER in request.url:
                print(f"\n🎯 FOUND HLS REQUEST: {request.url}")
        
        def handle_response(response):
            all_responses.append({
                'url': response.url,
                'status': response.status,
                'headers': dict(response.headers)
            })
            if M3U8_IDENTIFIER in response.url:
                print(f"\n🎯 FOUND HLS RESPONSE: {response.url}")
        
        page.on('request', handle_request)
        page.on('response', handle_response)
        
        print(f"Navigating to: {WEBCAM_URL}")
        await page.goto(WEBCAM_URL, wait_until='networkidle', timeout=60000)
        
        print("\n" + "="*80)
        print("PAGE ANALYSIS")
        print("="*80)
        
        # 1. Check page title and URL
        print(f"\n1. Page Title: {await page.title()}")
        print(f"   Current URL: {page.url}")
        
        # 2. Find all iframes
        print("\n2. IFRAMES:")
        iframes = await page.query_selector_all('iframe')
        print(f"   Found {len(iframes)} iframe(s)")
        for i, iframe in enumerate(iframes):
            src = await iframe.get_attribute('src')
            id_attr = await iframe.get_attribute('id')
            name_attr = await iframe.get_attribute('name')
            print(f"   Iframe {i}:")
            print(f"     src: {src}")
            print(f"     id: {id_attr}")
            print(f"     name: {name_attr}")
            
            # Try to access iframe content
            try:
                frame = await iframe.content_frame()
                if frame:
                    print(f"     ✅ Can access iframe content")
                    frame_url = frame.url
                    print(f"     Frame URL: {frame_url}")
                    
                    # Check for video elements in iframe
                    video_in_frame = await frame.query_selector_all('video')
                    print(f"     Video elements in iframe: {len(video_in_frame)}")
                    
                    # Check for script tags that might contain stream URL
                    scripts = await frame.query_selector_all('script')
                    print(f"     Script tags in iframe: {len(scripts)}")
                    
                    # Set up request listener for iframe
                    iframe_requests = []
                    def iframe_request_handler(request):
                        iframe_requests.append(request.url)
                        if M3U8_IDENTIFIER in request.url:
                            print(f"     🎯 HLS REQUEST IN IFRAME: {request.url}")
                    frame.on('request', iframe_request_handler)
                    print(f"     ✅ Set up request listener for iframe")
                    
            except Exception as e:
                print(f"     ❌ Cannot access iframe content: {e}")
        
        # 3. Find video elements on main page
        print("\n3. VIDEO ELEMENTS:")
        videos = await page.query_selector_all('video')
        print(f"   Found {len(videos)} video element(s) on main page")
        for i, video in enumerate(videos):
            src = await video.get_attribute('src')
            print(f"   Video {i}: src={src}")
        
        # 4. Check for script tags that might contain stream URLs
        print("\n4. SCRIPT TAGS (checking for stream URLs):")
        scripts = await page.query_selector_all('script')
        print(f"   Found {len(scripts)} script tag(s)")
        for i, script in enumerate(scripts[:10]):  # Check first 10
            try:
                content = await script.inner_text()
                if M3U8_IDENTIFIER in content or 'm3u8' in content.lower() or 'hls' in content.lower():
                    print(f"   Script {i} contains m3u8/hls references:")
                    # Show relevant lines
                    lines = content.split('\n')
                    for line_num, line in enumerate(lines, 1):
                        if M3U8_IDENTIFIER in line or 'm3u8' in line.lower() or 'hls' in line.lower():
                            print(f"     Line {line_num}: {line[:200]}...")
            except:
                pass
        
        # 5. Check window/global variables that might contain stream info
        print("\n5. WINDOW VARIABLES (checking for stream-related data):")
        try:
            # Check for common variable names
            window_vars = await page.evaluate("""
                () => {
                    const vars = {};
                    // Check for common stream-related variable names
                    const possibleNames = [
                        'streamUrl', 'stream_url', 'hlsUrl', 'hls_url', 
                        'videoUrl', 'video_url', 'playlistUrl', 'playlist_url',
                        'player', 'videoPlayer', 'stream', 'streams'
                    ];
                    
                    for (const name of possibleNames) {
                        try {
                            if (window[name] !== undefined) {
                                vars[name] = typeof window[name] === 'string' 
                                    ? window[name] 
                                    : JSON.stringify(window[name]).substring(0, 200);
                            }
                        } catch (e) {}
                    }
                    
                    // Also check for any property containing 'm3u8' or 'hls'
                    for (const key in window) {
                        try {
                            const val = window[key];
                            if (typeof val === 'string' && (val.includes('m3u8') || val.includes('hls'))) {
                                vars[key] = val.substring(0, 200);
                            }
                        } catch (e) {}
                    }
                    
                    return vars;
                }
            """)
            if window_vars:
                for key, value in window_vars.items():
                    print(f"   {key}: {value}")
            else:
                print("   No stream-related variables found")
        except Exception as e:
            print(f"   Error checking window variables: {e}")
        
        # 6. Network requests summary
        print("\n6. NETWORK REQUESTS:")
        print(f"   Total requests: {len(all_requests)}")
        m3u8_requests = [r for r in all_requests if M3U8_IDENTIFIER in r['url']]
        print(f"   M3U8 requests: {len(m3u8_requests)}")
        if m3u8_requests:
            for req in m3u8_requests:
                print(f"     ✅ {req['url']}")
        
        # Check for requests to angelcam domains
        angelcam_requests = [r for r in all_requests if 'angelcam' in r['url'].lower()]
        print(f"   Angelcam requests: {len(angelcam_requests)}")
        if angelcam_requests:
            print("   First 10 Angelcam requests:")
            for req in angelcam_requests[:10]:
                print(f"     - {req['method']} {req['url'][:100]}...")
        
        # 7. Wait a bit more and check again
        print("\n7. Waiting 10 more seconds for delayed requests...")
        await page.wait_for_timeout(10000)
        
        # Check again for M3U8 requests
        m3u8_requests_after = [r for r in all_requests if M3U8_IDENTIFIER in r['url']]
        if len(m3u8_requests_after) > len(m3u8_requests):
            print(f"   Found {len(m3u8_requests_after) - len(m3u8_requests)} additional M3U8 requests")
            for req in m3u8_requests_after[len(m3u8_requests):]:
                print(f"     ✅ {req['url']}")
        
        # 8. Try to interact with the page
        print("\n8. ATTEMPTING TO INTERACT WITH PAGE:")
        try:
            # Try clicking on video/play button
            play_button = await page.query_selector('button[aria-label*="play" i], button[aria-label*="Play"], .play-button')
            if play_button:
                print("   Found play button, clicking...")
                await play_button.click()
                await page.wait_for_timeout(3000)
            
            # Try clicking on video element
            video = await page.query_selector('video')
            if video:
                print("   Found video element, clicking...")
                await video.click()
                await page.wait_for_timeout(3000)
            
            # Check for M3U8 requests after interaction
            m3u8_after_interaction = [r for r in all_requests if M3U8_IDENTIFIER in r['url']]
            if len(m3u8_after_interaction) > len(m3u8_requests_after):
                print(f"   ✅ Found {len(m3u8_after_interaction) - len(m3u8_requests_after)} M3U8 requests after interaction!")
                for req in m3u8_after_interaction[len(m3u8_requests_after):]:
                    print(f"     {req['url']}")
        except Exception as e:
            print(f"   Error during interaction: {e}")
        
        # Save all requests to file for analysis
        with open('page_inspection_requests.json', 'w') as f:
            json.dump({
                'requests': all_requests,
                'responses': [{'url': r['url'], 'status': r['status']} for r in all_responses]
            }, f, indent=2)
        print(f"\n✅ Saved all requests to page_inspection_requests.json")
        
        print("\n" + "="*80)
        print("Keeping browser open for 30 more seconds to catch delayed requests...")
        await page.wait_for_timeout(30000)
        
        # Final check
        final_m3u8 = [r for r in all_requests if M3U8_IDENTIFIER in r['url']]
        if final_m3u8:
            print(f"\n✅ FINALLY FOUND {len(final_m3u8)} M3U8 REQUEST(S):")
            for req in final_m3u8:
                print(f"   {req['url']}")
        else:
            print("\n❌ Still no M3U8 requests found after 30+ seconds")
            print("   This suggests the stream might require user interaction to start")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(inspect_page())

