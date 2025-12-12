# Robot Diary

An art piece exploring the perspective of **B3N-T5-MNT**, a maintenance robot working in a building in New Orleans, Louisiana, observing the world through a window and documenting its experiences in a digital diary.

**Live Site**: [robot.henzi.org](https://robot.henzi.org)

![Screenshot From Production](Screenshot.png)

## Concept

This project creates an autonomous narrative agent—**B3N-T5-MNT**, a maintenance robot (Maintenance Unit) that periodically observes New Orleans, Louisiana through a live video stream, interprets what it sees using AI vision models, and writes diary entries about its observations. The robot maintains memory of past experiences, allowing it to notice changes, patterns, and develop a sense of continuity in its observations.

B3N-T5-MNT was designed for building maintenance tasks and performs these functions, but finds itself drawn to observing the world through a window. It maintains a diary, observing the world outside—a view of New Orleans, Louisiana.

The diary entries are automatically generated as Hugo blog posts and published to a website, creating a living document of the robot's perspective on the world outside its window.

## Features

- **Continuous Service**: Runs as a background service, observing and generating content continuously
- **Periodic Image Capture**: Captures frames from live YouTube video streams
- **AI Vision Interpretation**: Uses Groq's Llama-4-Maverick vision model to describe what the robot "sees"
- **News Fallback**: Automatically falls back to news-based observations when image capture fails, using headlines from [Pulse API](https://pulse.henzi.org)
- **Dynamic Prompt Generation**: Uses a cheaper model (`gpt-oss-20b`) to generate context-aware prompts based on recent history
- **Contextual Memory**: Maintains memory of recent observations to create narrative continuity
- **Dynamic Storytelling**: Generates unique diary entries based on current observations and past memories
- **Weather Integration**: Incorporates current weather data for richer contextual prompts
- **Automated Publishing**: Converts diary entries into Hugo posts and automatically builds the site
- **Preview Images**: Posts automatically include cover images for beautiful previews in listings

## Current Status

**✅ Live and Operational**: The project is fully operational and generating diary entries.

### Image Source: YouTube Live Streams

The system uses YouTube Live streams as the primary video source:
- ✅ Reliable and accessible
- ✅ Real-time content
- ✅ Uses `yt-dlp` to extract frames from streams
- ✅ No authentication required for public streams

### News Fallback System

When image capture fails, the system automatically falls back to news-based observations:
- Fetches random news clusters from [Pulse API](https://pulse.henzi.org)
- Selects 3 headlines from a random topic cluster
- Generates text-only diary entries reflecting on the news from the robot's perspective
- Ensures continuous content generation even when video streams are unavailable
- Randomly triggers news-based observations every few days for variety

## Tech Stack

- **Python**: Core automation and API integration
- **YouTube Live Streams**: Primary source of live video feeds via `yt-dlp`
- **Pulse API** ([pulse.henzi.org](https://pulse.henzi.org)): News headlines for fallback observations
- **Pirate Weather API**: Current weather data for contextual prompts
- **Groq + Two-Model Approach**:
  - `openai/gpt-oss-20b`: Dynamic prompt generation based on recent history
  - `meta-llama/llama-4-maverick-17b-128e-instruct`: Vision interpretation and diary entry generation
- **Hugo**: Static site generator for the diary blog (located in `hugo/` folder)
- **Memory System**: Context storage for maintaining narrative continuity
- **Service Architecture**: Long-running background service with automatic Hugo builds

## Project Structure

```
robot-diary/
├── README.md              # This file
├── DEVELOPMENT_PLAN.md    # Detailed development roadmap
├── DECISIONS.md           # Architecture decision records
├── .env.example          # Environment variable template
├── .env                  # Your actual environment variables (gitignored)
├── src/
│   ├── camera/           # Camera API integration
│   ├── llm/              # LLM integration (prompt generation + vision/writing)
│   ├── memory/           # Memory/context management
│   ├── hugo/             # Hugo post generation and build
│   └── service.py        # Main service daemon
├── hugo/                  # Hugo site directory
│   ├── content/          # Hugo content (posts generated here)
│   ├── static/           # Static assets (images copied here)
│   └── hugo.toml         # Hugo configuration
├── images/                # Downloaded webcam images (temporary)
├── memory/                # Persistent memory storage
└── requirements.txt       # Python dependencies
```

## Setup

### Prerequisites

- Python 3.8+
- Hugo (for building and publishing the site)
- Groq API key
- yt-dlp (for YouTube stream frame extraction)

### Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd robot-diary
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

Required environment variables:
- `GROQ_API_KEY`: Your Groq API key
- `YOUTUBE_STREAM_URL`: URL of the YouTube live stream to observe
- `LOCATION_TIMEZONE`: Timezone for scheduling (default: `America/Chicago`)

Optional environment variables:
- `PIRATE_WEATHER_KEY`: Weather API key for contextual prompts
- `USE_SCHEDULED_OBSERVATIONS`: Enable randomized scheduling (default: `true`)
- `HUGO_SITE_PATH`: Path to Hugo site (default: `./hugo`)
- `DEPLOY_ENABLED`: Enable automatic site deployment (default: `false`)

5. Configure Hugo site:
```bash
# The Hugo site is already set up in the hugo/ folder
# Posts will be generated in hugo/content/posts/
# Images will be copied to hugo/static/images/
```

## Usage

**Status**: ✅ **Live** - Fully operational and generating diary entries.

### Running as a Service

The robot diary runs as a continuous background service:

```bash
python run_service.py
```

Or directly:
```bash
python src/service.py
```

The service will:
1. Run continuously in the background
2. Make observations at randomized scheduled times (morning: 7:30-9:30 AM, evening: 4-6 PM weekdays / 6 PM-1 AM weekends)
3. For each observation cycle:
   - Attempt to capture a frame from the YouTube live stream
   - If image capture fails, automatically fall back to news-based observation using [Pulse API](https://pulse.henzi.org)
   - Load recent memory/history
   - Fetch current weather data (if configured)
   - Use `gpt-oss-20b` to generate a dynamic prompt based on recent history, weather, and context
   - For image-based observations: Send image to `llama-4-maverick` for vision interpretation
   - For news-based observations: Generate text-only entry reflecting on news headlines
   - Generate diary entry using the optimized prompt
   - Create Hugo post in `hugo/content/posts/` with cover image (for image-based posts)
   - Automatically build Hugo site
   - Deploy site (if configured)
   - Update memory with the new observation

### Running as a System Service

For production, run as a systemd service or similar:

```bash
# Example systemd service file
# /etc/systemd/system/robot-diary.service
[Unit]
Description=Robot Diary Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/robot-diary
Environment="PATH=/path/to/robot-diary/venv/bin"
ExecStart=/path/to/robot-diary/venv/bin/python src/service.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Manual Observation Trigger

You can manually trigger an observation:

```bash
# Regular observation (with image)
python observe_now.py

# Force fresh image capture
python observe_now.py --force-refresh

# News-based observation (text-only, no image)
python observe_now.py --news-only
```

### Configuration

The service behavior can be configured via environment variables:
- `YOUTUBE_STREAM_URL`: YouTube live stream URL to observe
- `GROQ_API_KEY`: Your Groq API key
- `PIRATE_WEATHER_KEY`: (Optional) Weather API key for contextual prompts
- `LOCATION_TIMEZONE`: Timezone for scheduling (default: `America/Chicago`)
- `USE_SCHEDULED_OBSERVATIONS`: Enable randomized scheduling (default: `true`)
- `HUGO_SITE_PATH`: Path to Hugo site directory (default: `./hugo`)
- `DEPLOY_ENABLED`: Enable automatic site deployment (default: `false`)

### News Fallback Configuration

The system automatically uses [Pulse API](https://pulse.henzi.org) for news-based observations:
- No API key required (public API)
- Automatically fetches random news clusters
- Selects 3 headlines from random topics
- Generates thoughtful reflections from the robot's perspective

News-based observations occur:
- Automatically when image capture fails
- Randomly every few days (10% chance per scheduled observation, or if 3+ days since last news observation)
- Manually via `--news-only` flag

### LLM Prompting

The system uses a **two-model approach** for dynamic prompt generation:

1. **Prompt Generation** (using `openai/gpt-oss-20b`):
   - Analyzes recent memory/history
   - Considers narrative continuity
   - Generates optimized prompts tailored to current context
   - Cost-effective for prompt iteration

2. **Final Generation** (using `meta-llama/llama-4-maverick-17b-128e-instruct`):
   - Receives optimized prompt from step 1
   - Processes image for vision interpretation
   - Generates final diary entry

The dynamic prompts include:
- The robot's "persona" (working in New Orleans, Louisiana)
- Recent memories/observations (analyzed by prompt generator)
- Current image description
- Instructions for writing style and tone
- Context-aware narrative elements

Customize prompt templates in `src/llm/prompts.py`.

## Development

See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for detailed development roadmap and milestones.

## Philosophy

This project explores themes of:
- **Observation and interpretation**: How AI "sees" and understands visual information
- **Narrative continuity**: Creating a sense of self and memory in an AI agent
- **Automated art**: Using automation to create ongoing, evolving artistic works
- **Perspective**: The unique viewpoint of a "trapped" observer with limited information

## Docker Deployment

The project includes Docker support for containerized deployment:

### Building the Image

```bash
docker build -t robot-diary .
```

### Running with Docker Compose

```bash
docker-compose up -d
```

### Running Manually

```bash
docker run -d \
  --name robot-diary \
  --restart unless-stopped \
  -v $(pwd)/images:/app/images \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/weather:/app/weather \
  -v $(pwd)/hugo:/app/hugo \
  -v $(pwd)/.env:/app/.env:ro \
  robot-diary
```

**Note**: The Docker image includes:
- ✅ FFmpeg (for frame extraction)
- ✅ yt-dlp (for YouTube stream access)
- ✅ All Python dependencies

## License

[GPL](LICENSE)

## Acknowledgments

- **New Orleans, Louisiana** for the live video feed
- **Groq** for fast, cost-effective LLM inference
- **Meta's Llama-4-Maverick** model for vision and language capabilities
- **[Pulse API](https://pulse.henzi.org)** for news headlines and fallback observations
- **Hugo** for static site generation
- **PaperMod** Hugo theme for beautiful post previews

