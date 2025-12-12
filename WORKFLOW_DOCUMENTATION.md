# Robot Diary Workflow Documentation

This document provides detailed information about the observation cycle workflow, timing, API calls, and requirements for auditing and future development.

## Table of Contents

1. [Observation Cycle Overview](#observation-cycle-overview)
2. [Detailed Step-by-Step Workflow](#detailed-step-by-step-workflow)
3. [Timing and Performance](#timing-and-performance)
4. [API Call Patterns](#api-call-patterns)
5. [Caching Strategy](#caching-strategy)
6. [Dynamic Prompting Requirements](#dynamic-prompting-requirements)
7. [Future Enhancements](#future-enhancements)

---

## Observation Cycle Overview

The Robot Diary service runs a continuous observation cycle that:

1. **Fetches** the latest webcam image (with intelligent caching)
2. **Loads** recent memory/observations
3. **Generates** a dynamic prompt based on context
4. **Creates** a diary entry using vision AI
5. **Saves** the observation to memory
6. **Generates** a Hugo blog post
7. **Builds** the Hugo static site

**Cycle Frequency**: Configurable via `OBSERVATION_INTERVAL_HOURS` (default: 6 hours)

**Initial Behavior**: Runs immediately on service start, then waits for the configured interval

---

## Detailed Step-by-Step Workflow

### Step 1: Fetch Latest Webcam Image

**Module**: `src/camera/fetcher.py`  
**Function**: `fetch_latest_image(force_refresh=False)`

**Process**:
1. **API Call**: `GET https://api.windy.com/webcams/api/v3/webcams/{WEBCAM_ID}?include=images`
   - Headers: `X-WINDY-API-KEY: {API_KEY}`
   - Purpose: Get current image URL
   - **Always called** (minimal API call to check for updates)

2. **Cache Check**:
   - Loads cache metadata from `images/.cache_metadata.json`
   - Compares image URL hash with cached hash
   - If hash matches and file exists → **Use cached image** (no download)
   - If hash differs or file missing → **Download new image**

3. **Image Download** (if needed):
   - Downloads from image URL (typically `preview` size)
   - Saves to `images/webcam_{timestamp}_{hash}.jpg`
   - Updates cache metadata

**Output**: `Path` object pointing to image file

**Caching Behavior**:
- ✅ **Cached**: If image URL hasn't changed
- ❌ **Downloaded**: If URL changed or cache missing
- **Cache Location**: `images/.cache_metadata.json` + image files

**Estimated Time**: 
- Cache hit: ~100-200ms (API check only)
- Cache miss: ~200-500ms (API check + download)

---

### Step 2: Load Recent Memory

**Module**: `src/memory/manager.py`  
**Function**: `get_recent_memory(count=10)`

**Process**:
1. **File Read**: Loads `memory/observations.json`
2. **Filter**: Returns last N entries (default: 10)
3. **Format**: Returns list of observation dictionaries

**Data Structure**:
```json
{
  "id": 1,
  "date": "2025-12-11T22:51:06",
  "image_path": "images/webcam_20251211_225104_6bedbbac.jpg",
  "image_filename": "webcam_20251211_225104_6bedbbac.jpg",
  "image_url": "https://...",
  "content": "Diary entry text...",
  "summary": "First 200 chars..."
}
```

**Output**: `List[Dict]` of recent observations

**Estimated Time**: <10ms (file I/O)

---

### Step 3: Generate Dynamic Prompt

**Module**: `src/llm/client.py`  
**Function**: `generate_prompt(recent_memory, base_prompt_template)`

**Process**:
1. **Format Memory**: Converts recent memory to text format
   - Takes last 5 entries
   - Formats as: `- {date}: {summary}`

2. **API Call**: `POST https://api.groq.com/openai/v1/chat/completions`
   - Model: `openai/gpt-oss-20b` (cheaper model)
   - Purpose: Generate context-aware prompt
   - Input: Recent memory + base prompt template
   - Output: Optimized prompt string

3. **Fallback**: If API fails, uses base prompt template

**Prompt Generation Logic**:
```
System: "You are a prompt optimization assistant."
User: "Generate optimized prompt based on:
  - Recent observations: [memory]
  - Base template: [template]
  Requirements:
  1. Reference recent observations
  2. Maintain narrative continuity
  3. Guide thoughtful, reflective writing
  4. Help notice changes/patterns"
```

**Output**: Optimized prompt string (max 500 tokens)

**Estimated Time**: ~500-1000ms (API latency)

**Current Limitations**:
- ❌ Does not include current date/time
- ❌ Does not include weather information
- ❌ Does not include time of day context
- ✅ Includes recent memory/observations

---

### Step 4: Create Diary Entry

**Module**: `src/llm/client.py`  
**Function**: `create_diary_entry(image_path, optimized_prompt)`

**Process**:
1. **Image Encoding**: 
   - Reads image file
   - Base64 encodes for API

2. **API Call**: `POST https://api.groq.com/openai/v1/chat/completions`
   - Model: `meta-llama/llama-4-maverick-17b-128e-instruct` (vision model)
   - Purpose: Generate diary entry from image
   - Input: 
     - Optimized prompt (from Step 3)
     - Base64-encoded image
   - Output: Diary entry text

3. **Prompt Construction**:
   ```
   {optimized_prompt}
   
   Write a diary entry as if you are a robot trapped in downtown Cincinnati, 
   observing the world through this webcam view. Be thoughtful, reflective, 
   and notice details. Reference your recent memories if relevant.
   ```

**Output**: Diary entry text (max 1000 tokens, typically 2000-3000 characters)

**Estimated Time**: ~1500-3000ms (API latency + image processing)

**Current Limitations**:
- ❌ No explicit date/time context in prompt
- ❌ No weather context
- ❌ No seasonal/temporal awareness
- ✅ Has access to recent memory via optimized prompt

---

### Step 5: Save to Memory

**Module**: `src/memory/manager.py`  
**Function**: `add_observation(image_path, diary_entry, image_url)`

**Process**:
1. **Load Memory**: Reads current `memory/observations.json`
2. **Create Entry**: 
   - Generates new observation ID
   - Creates entry with:
     - ID, date (ISO format), image paths, content, summary
3. **Cleanup**: 
   - Removes entries older than `MEMORY_RETENTION_DAYS` (default: 30)
   - Limits to `MAX_MEMORY_ENTRIES` (default: 50)
4. **Save**: Writes updated memory to file

**Output**: None (side effect: updates memory file)

**Estimated Time**: <50ms (file I/O)

---

### Step 6: Generate Hugo Post

**Module**: `src/hugo/generator.py`  
**Function**: `create_post(diary_entry, image_path, observation_id)`

**Process**:
1. **Copy Image**: 
   - Copies image to `hugo/static/images/`
   - Renames: `observation_{id}_{original_filename}`

2. **Generate Front Matter**:
   ```yaml
   +++
   date = "{ISO timestamp}"
   draft = false
   title = "Observation #{id}"
   tags = ["robot-diary", "observation"]
   +++
   ```

3. **Generate Markdown**:
   - Image markdown: `![Observation #{id}](/images/{filename})`
   - Diary entry content

4. **Write File**: Saves to `hugo/content/posts/{date}_observation_{id}.md`

**Output**: `Path` to created post file

**Estimated Time**: ~50-100ms (file I/O + image copy)

---

### Step 7: Build Hugo Site

**Module**: `src/hugo/generator.py`  
**Function**: `build_site()`

**Process**:
1. **Check Flag**: If `HUGO_BUILD_ON_UPDATE=false`, skip
2. **Execute**: Runs `hugo` command in `HUGO_SITE_PATH`
3. **Output**: Hugo generates static site in `hugo/public/`

**Output**: Boolean (success/failure)

**Estimated Time**: ~2-10 seconds (depends on site size)

**Note**: Can be disabled via `HUGO_BUILD_ON_UPDATE=false` environment variable

---

## Timing and Performance

### Complete Cycle Timing

| Step | Component | Estimated Time | API Calls |
|------|-----------|----------------|-----------|
| 1. Fetch Image | Windy API | 100-500ms | 1 (always) |
| 2. Load Memory | File I/O | <10ms | 0 |
| 3. Generate Prompt | Groq API | 500-1000ms | 1 |
| 4. Create Diary | Groq API | 1500-3000ms | 1 |
| 5. Save Memory | File I/O | <50ms | 0 |
| 6. Generate Post | File I/O | 50-100ms | 0 |
| 7. Build Hugo | Hugo CLI | 2-10s | 0 |
| **Total** | | **~4-15 seconds** | **3 API calls** |

### Typical Cycle (with cache hit):
- **Fastest**: ~4-5 seconds (cached image, fast APIs)
- **Average**: ~6-8 seconds
- **Slowest**: ~12-15 seconds (new image download, slow APIs, large Hugo build)

### Service Loop Timing

- **Initial Observation**: Runs immediately on start
- **Subsequent Observations**: Every `OBSERVATION_INTERVAL_HOURS` (default: 6)
- **Sleep Behavior**: Checks for shutdown every 60 seconds during sleep
- **Error Recovery**: Waits 60 seconds before retrying on error

---

## API Call Patterns

### Windy Webcams API

**Endpoint**: `GET https://api.windy.com/webcams/api/v3/webcams/{WEBCAM_ID}?include=images`

**Frequency**: 
- **Once per cycle** (always called to check for URL changes)
- **Minimal overhead**: Only checks URL, doesn't download unless changed

**Rate Limiting**: 
- Not explicitly documented
- Current implementation: 1 call per observation cycle
- With 6-hour intervals: ~4 calls/day maximum

**Caching Strategy**:
- URL hash comparison prevents redundant downloads
- Cache metadata persists between cycles
- Image files cached indefinitely (manual cleanup needed)

### Groq API

**Endpoint**: `POST https://api.groq.com/openai/v1/chat/completions`

**Calls per Cycle**: **2**

1. **Prompt Generation** (`gpt-oss-20b`):
   - Model: `openai/gpt-oss-20b`
   - Max tokens: 500
   - Temperature: 0.7
   - Frequency: Once per cycle

2. **Diary Creation** (`llama-4-maverick`):
   - Model: `meta-llama/llama-4-maverick-17b-128e-instruct`
   - Max tokens: 1000
   - Temperature: 0.8
   - Includes base64 image
   - Frequency: Once per cycle

**Total API Calls per Cycle**: 2 Groq calls

**Daily API Usage** (6-hour intervals):
- Groq calls: ~8 calls/day (4 cycles × 2 calls)
- Windy calls: ~4 calls/day (4 cycles × 1 call)

**Cost Optimization**:
- Uses cheaper model (`gpt-oss-20b`) for prompt generation
- Caches images to avoid redundant processing
- No redundant API calls within a cycle

---

## Caching Strategy

### Image Caching

**Location**: `images/.cache_metadata.json`

**Cache Metadata Structure**:
```json
{
  "latest_hash": "md5_hash_of_image_url",
  "latest_path": "webcam_20251211_225104_6bedbbac.jpg",
  "latest_url": "https://imgproxy.windy.com/...",
  "fetched_at": "2025-12-11T22:51:04",
  "webcam_id": "1735072832"
}
```

**Cache Logic**:
1. Always check API for current image URL
2. Compare URL hash with cached hash
3. If hash matches → use cached file (no download)
4. If hash differs → download new image

**Benefits**:
- Prevents redundant downloads
- Reduces bandwidth usage
- Faster cycle times when image unchanged

**Limitations**:
- Cache never expires automatically
- Old images accumulate (manual cleanup needed)
- Hash collision possible (very unlikely with MD5)

### Memory Caching

**Location**: `memory/observations.json`

**Persistence**: 
- All observations stored in single JSON file
- Loaded on each cycle
- Automatically cleaned (old entries removed)

**Retention**:
- Default: 30 days
- Configurable via `MEMORY_RETENTION_DAYS`
- Max entries: 50 (configurable via `MAX_MEMORY_ENTRIES`)

---

## Dynamic Prompting Requirements

### Current State

**What's Included**:
- ✅ Recent memory/observations (last 5 entries)
- ✅ Base prompt template (robot persona)
- ✅ Context-aware prompt generation

**What's Missing**:
- ❌ Current date and time
- ❌ Weather information
- ❌ Time of day context
- ❌ Seasonal awareness
- ❌ Day of week context

### Requirements for Enhanced Dynamic Prompting

#### 1. Date and Time Context

**Requirement**: Include current date, time, day of week, and season in prompt generation.

**Implementation Needs**:
- Pass `datetime.now()` to prompt generation
- Format: "Today is {day}, {date} at {time}"
- Include: Day of week, date, time, season
- Timezone: Use system timezone or configure (Cincinnati timezone)

**Example Context**:
```
Current Context:
- Date: December 11, 2025
- Time: 10:51 PM EST
- Day of Week: Wednesday
- Season: Winter
```

**Benefits**:
- Robot can reference specific dates
- Time-aware observations (morning vs evening)
- Seasonal context (winter vs summer)
- Day-specific patterns (weekday vs weekend)

#### 2. Weather Information

**Requirement**: Fetch and include current weather conditions for Cincinnati.

**Implementation Needs**:
- Weather API integration (e.g., OpenWeatherMap, Weather.gov)
- Fetch: Temperature, conditions, humidity, wind
- Cache: Weather data (update every 15-30 minutes)
- Location: Cincinnati, OH coordinates or zip code

**Example Context**:
```
Weather Context:
- Temperature: 42°F
- Conditions: Partly Cloudy
- Humidity: 65%
- Wind: 8 mph NW
- Visibility: 10 miles
```

**Benefits**:
- Robot can comment on weather
- Correlate visual observations with weather
- Notice weather-related changes
- Seasonal weather patterns

**API Options**:
1. **OpenWeatherMap** (free tier: 60 calls/min)
2. **Weather.gov** (free, no API key needed)
3. **WeatherAPI.com** (free tier: 1M calls/month)

**Caching Strategy**:
- Cache weather for 15-30 minutes
- Update before each observation cycle
- Store in memory or separate cache file

#### 3. Enhanced Prompt Generation

**Updated Prompt Generation Input**:
```
Context for Prompt Generation:
- Current Date/Time: {datetime}
- Weather: {weather_data}
- Recent Observations: {memory}
- Base Template: {template}

Generate optimized prompt that:
1. References specific date/time context
2. Incorporates weather observations
3. Maintains narrative continuity with recent memory
4. Guides robot to notice weather-related visual changes
5. Creates time-aware reflections
```

**Example Enhanced Prompt Output**:
```
You are observing downtown Cincinnati on a cold Wednesday evening in December. 
The temperature is 42°F with partly cloudy skies. 

In your recent observations, you noted [reference to recent memory]. 
Today, consider how the winter evening light differs from previous observations, 
and how the weather might affect what you see in the webcam view. Notice if 
people are dressed for the cold, if the streets are wet from recent weather, 
or if the lighting reflects the time of day and season.
```

---

## Future Enhancements

### Phase 1: Date/Time Integration (High Priority)

**Tasks**:
- [ ] Add datetime context to prompt generation
- [ ] Format date/time for prompt inclusion
- [ ] Add timezone configuration
- [ ] Update prompt templates to use date/time

**Estimated Effort**: 2-4 hours

### Phase 2: Weather Integration (High Priority)

**Tasks**:
- [ ] Research and select weather API
- [ ] Implement weather fetching module
- [ ] Add weather caching (15-30 min TTL)
- [ ] Integrate weather into prompt generation
- [ ] Add weather to memory/observations

**Estimated Effort**: 4-6 hours

**API Recommendation**: Weather.gov (free, no key, reliable)

### Phase 3: Enhanced Context Awareness

**Tasks**:
- [ ] Combine date/time + weather + memory in prompts
- [ ] Add seasonal awareness
- [ ] Time-of-day specific observations
- [ ] Weather-visual correlation prompts

**Estimated Effort**: 2-3 hours

### Phase 4: Additional Context Sources (Future)

**Potential Additions**:
- News headlines (local Cincinnati news)
- Traffic conditions
- Events calendar (holidays, festivals)
- Sunrise/sunset times
- Moon phase

---

## Requirements Summary

### Current System Requirements

1. **API Keys**:
   - Windy Webcams API key
   - Groq API key

2. **Dependencies**:
   - Python 3.8+
   - Hugo (for site building)
   - Internet connection

3. **Storage**:
   - Images directory (cached webcam images)
   - Memory directory (observations JSON)
   - Hugo site directory

### Enhanced System Requirements (Future)

1. **Additional API Keys** (if using paid weather service):
   - Weather API key (if not using Weather.gov)

2. **Additional Dependencies**:
   - Weather API client library (if needed)

3. **Configuration**:
   - Timezone setting
   - Weather API configuration
   - Weather cache TTL

---

## Monitoring and Auditing

### Logging

**Log File**: `robot_diary.log`

**Log Levels**:
- INFO: Normal operation steps
- DEBUG: Detailed information (prompts, etc.)
- ERROR: Failures and exceptions
- WARNING: Fallbacks and recoveries

### Metrics to Track

1. **Cycle Timing**: How long each cycle takes
2. **API Call Count**: Track API usage
3. **Cache Hit Rate**: How often images are cached
4. **Error Rate**: Failed cycles
5. **Memory Growth**: Number of stored observations

### Audit Points

1. **API Usage**: Monitor Groq and Windy API calls
2. **Cost Tracking**: Track API costs (especially Groq)
3. **Storage Growth**: Monitor image and memory file sizes
4. **Hugo Build Time**: Track site build performance
5. **Error Patterns**: Identify recurring issues

---

## Configuration Reference

### Environment Variables

```bash
# Required
WINDY_WEBCAMS_API_KEY=your_key
GROQ_API_KEY=your_key

# Optional (with defaults)
WEBCAM_ID=1735072832
OBSERVATION_INTERVAL_HOURS=6
HUGO_SITE_PATH=./hugo
HUGO_BUILD_ON_UPDATE=true
MEMORY_RETENTION_DAYS=30
MAX_MEMORY_ENTRIES=50
```

### Future Configuration Additions

```bash
# Weather API (if needed)
WEATHER_API_KEY=your_key
WEATHER_API_PROVIDER=weather_gov  # or openweathermap, etc.
WEATHER_CACHE_TTL_MINUTES=30

# Timezone
TIMEZONE=America/New_York  # Cincinnati timezone
```

---

## Conclusion

The current implementation provides a solid foundation with:
- ✅ Intelligent image caching
- ✅ Memory-based context awareness
- ✅ Two-model LLM approach for cost efficiency
- ✅ Automatic Hugo site generation

**Next Steps for Enhancement**:
1. Add date/time context to prompts
2. Integrate weather API
3. Enhance prompt generation with temporal awareness
4. Add weather-visual correlation

This will create a more contextually aware robot that can make time-sensitive and weather-aware observations, enhancing the narrative quality and authenticity of the diary entries.

