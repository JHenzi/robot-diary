# Robot Diary

An art piece exploring the perspective of **B3N-T5-MNT**, a maintenance robot trapped in downtown Cincinnati, observing the world through a window and documenting its experiences in a digital diary.

**Live Site**: [robot.henzi.org](https://robot.henzi.org)

## Concept

This project creates an autonomous narrative agent—**B3N-T5-MNT**, a maintenance robot (Maintenance Unit) that periodically observes downtown Cincinnati through a webcam feed, interprets what it sees using AI vision models, and writes diary entries about its observations. The robot maintains memory of past experiences, allowing it to notice changes, patterns, and develop a sense of continuity in its trapped existence.

B3N-T5-MNT was designed for building maintenance tasks but finds itself stuck, unable to perform its intended functions. Instead, it maintains a diary, observing the world through its only window—a view of downtown Cincinnati.

The diary entries are automatically generated as Hugo blog posts and published to a website, creating a living document of the robot's perspective on the world outside its window.

## Features

- **Continuous Service**: Runs as a background service, observing and generating content continuously
- **Periodic Image Capture**: Fetches preview images from the Windy webcams API at configurable intervals
- **AI Vision Interpretation**: Uses Groq's Llama-4-Maverick vision model to describe what the robot "sees"
- **Dynamic Prompt Generation**: Uses a cheaper model (`gpt-oss-20b`) to generate context-aware prompts based on recent history
- **Contextual Memory**: Maintains memory of recent observations to create narrative continuity
- **Dynamic Storytelling**: Generates unique diary entries based on current observations and past memories
- **Automated Publishing**: Converts diary entries into Hugo posts and automatically builds the site
- **Extensible**: Designed to expand to other activities like reading news, weather observations, etc.

## Tech Stack

- **Python**: Core automation and API integration
- **Windy Webcams API**: Source of downtown Cincinnati webcam images
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
- Windy Webcams API key
- Groq API key

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
- `WINDY_WEBCAMS_API_KEY`: Your Windy webcams API key
- `WEBCAM_ID`: The webcam ID for downtown Cincinnati (default: 1358084658)
- `GROQ_API_KEY`: Your Groq API key
- `OBSERVATION_INTERVAL_HOURS`: How often to make observations (default: 6)
- `HUGO_SITE_PATH`: Path to Hugo site (default: `./hugo`)

5. Configure Hugo site:
```bash
# The Hugo site is already set up in the hugo/ folder
# Posts will be generated in hugo/content/posts/
# Images will be copied to hugo/static/images/
```

## Usage

**Status**: ✅ **Working** - The service is operational and generating diary entries.

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
2. Make observations at configured intervals (default: every 6 hours)
3. For each observation cycle:
   - Fetch the latest webcam image
   - Load recent memory/history
   - Use `gpt-oss-20b` to generate a dynamic prompt based on recent history
   - Send image to `llama-4-maverick` for vision interpretation
   - Generate diary entry using the optimized prompt
   - Create Hugo post in `hugo/content/posts/`
   - Automatically build Hugo site
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

### Configuration

The service behavior can be configured via environment variables:
- `OBSERVATION_INTERVAL_HOURS`: How often to make observations (default: 6)
- `HUGO_SITE_PATH`: Path to Hugo site directory (default: `./hugo`)
- `HUGO_BUILD_ON_UPDATE`: Whether to auto-build Hugo (default: `true`)

## Configuration

### Webcam Selection

The default webcam ID (`1358084658`) should be the downtown Cincinnati view. To find other webcams:

1. Visit [Windy.com](https://www.windy.com)
2. Browse webcams in your desired location
3. Extract the webcam ID from the URL or API response
4. Update `WEBCAM_ID` in your `.env` file

### Memory Configuration

The memory system stores recent observations to provide context for new diary entries. Configure:
- Memory retention period
- Number of recent observations to include
- Memory storage format (JSON, database, etc.)

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
- The robot's "persona" (trapped in downtown Cincinnati)
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

## License

[Your License Here]

## Acknowledgments

- Windy.com for webcam API access
- Groq for fast, cost-effective LLM inference
- Meta's Llama-4-Maverick model for vision and language capabilities
- Hugo for static site generation

