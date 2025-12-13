# Robot Diary

An autonomous narrative agent—**B3N-T5-MNT**, a maintenance robot in New Orleans observing the world through a window and documenting its experiences in a digital diary.

**Live Site**: [robot.henzi.org](https://robot.henzi.org)

![Screenshot From Production](Screenshot.png)

## The Concept

B3N-T5-MNT is a maintenance robot that was designed for building maintenance but finds itself drawn to the window, observing Bourbon Street below. It captures frames from live video streams, interprets what it sees using AI vision models, and writes diary entries about its observations—creating a living document of a robot's perspective on the world.

But this isn't just "AI writes about photos." This project explores something more interesting: **how do you make an AI agent's writing feel alive, varied, and contextually aware?**

## The Novel Approach: Dynamic Context-Aware Prompting

Most AI writing projects use static prompts. We don't. Every diary entry is generated using a **dynamically constructed prompt** that combines:

### Rich World Context

The robot doesn't just see an image—it "knows" things about the world:

- **Temporal Awareness**: Date, time, season, day of week, whether it's a weekend
- **Holidays**: Detects US holidays (federal + cultural/religious) and mentions them naturally
- **Moon Phases**: Tracks full moons, new moons, and special lunar events
- **Astronomical Events**: Aware of solstices, equinoxes, and seasonal transitions
- **Sunrise/Sunset**: Knows when the sun rose or set, how long ago
- **Weather**: Current conditions, temperature, wind, precipitation—correlated with what it sees
- **News**: Randomly includes current news headlines (40% chance) so the robot can reference world events as if it overheard them
- **Seasonal Progress**: "We're in the middle of winter, with spring still 10 weeks away"

### Intelligent Memory System

The robot remembers past observations, but not by dumping full text into prompts:

- **LLM-Generated Summaries**: Each observation is distilled by an AI model (`llama-3.1-8b-instant`) into 200-400 character summaries that preserve:
  - Key visual details
  - Emotional tone
  - Notable events or patterns
  - References to people or objects
- **Narrative Continuity**: The robot can reference specific past observations, notice changes, and build on previous entries
- **Personality Drift**: As the robot accumulates more observations, its personality evolves (curious → reflective → philosophical)

### Prompt Variety Engine

To prevent repetitive, formulaic entries, each prompt includes randomly selected variety instructions:

- **Style Variations** (2 selected per entry): Narrative, philosophical, analytical, poetic, humorous, melancholic, speculative, anthropological, stream-of-consciousness, and more
- **Perspective Shifts**: Urgency, nostalgia, curiosity, wonder, detachment, self-awareness, mechanical curiosity, and 20+ other perspectives
- **Context-Aware Focus**: Instructions adapt to:
  - Time of day (morning routines vs. evening activities)
  - Weather conditions (wind effects, precipitation, visibility)
  - Location specifics (Bourbon Street characteristics, New Orleans culture)
  - Scene analysis (human interactions, movement patterns, architectural details)
- **Creative Challenges**: 60% chance of including a creative constraint (e.g., "Try an unexpected metaphor only a robot would think of")
- **Anti-Repetition Detection**: Analyzes recent entries to avoid repeating opening patterns or structures

### Multi-Model Architecture

We use a **three-model approach** for efficiency and quality:

1. **Memory Summarization** (`llama-3.1-8b-instant`): Cheap model distills each observation into a context-preserving summary
2. **Prompt Assembly** (direct template combination): Combines base template + context + variety instructions (bypasses expensive LLM optimization by default)
3. **Final Generation** (`llama-4-maverick-17b-128e-instruct`): Expensive vision model receives the rich, context-aware prompt and generates the diary entry

This architecture ensures:
- **Cost Efficiency**: Only the final generation uses the expensive model
- **Context Preservation**: No information loss through multiple LLM translations
- **Rich Output**: The vision model receives comprehensive context, not just an image

## What Makes This Different

### 1. World Knowledge, Not Just Vision

The robot doesn't just describe what it sees—it connects observations to:
- Current events (news headlines)
- Natural cycles (moon phases, seasons, sunrise/sunset)
- Cultural context (holidays, time of day patterns)
- Weather patterns (correlating visual observations with conditions)

### 2. True Narrative Continuity

Unlike systems that just append context, we use **intelligent summarization**:
- Each past observation is distilled to its essential context
- Summaries preserve emotional tone, key details, and references
- The robot can genuinely reference past observations without exhausting token limits
- Memory grows over time, creating a sense of accumulated experience

### 3. Guaranteed Variety

Every entry feels different because:
- **Random selection** of styles, perspectives, and focus areas
- **Anti-repetition detection** prevents formulaic openings
- **Context-aware instructions** adapt to current conditions
- **Explicit variety directives** in every prompt

### 4. Graceful Degradation

The system handles missing data elegantly:
- If moon phase calculation fails? Skip it, continue with other context
- If holidays library unavailable? Continue without holiday awareness
- If weather API fails? Use cached data or continue without weather
- **No data is fed to prompts if uncertain or missing**

## Example: What Goes Into a Prompt

Here's what the robot "knows" when writing an entry:

```
Today is Wednesday, December 25, 2025 at 10:51 PM CST. Today is Christmas Day. 
A full moon is visible. The sun set 5 hours ago. We're in the middle of winter, 
with spring still 10 weeks away. It is a weekday.

Weather Conditions:
The weather is Clear with a temperature of 45°F. The temperature has dropped 
3 degrees since my last observation.

Recent observations from the robot's memory:
[LLM-generated summaries of past 5-10 observations, each 200-400 chars]

PERSONALITY: The robot has been observing for a while. It may be developing a 
more reflective, contemplative mood...

STYLE VARIATION: For this entry, incorporate these approaches:
- Focus on sensory details - describe sounds, light, movement, textures
- Write more poetically - use poetic language, similes, metaphors

PERSPECTIVE: You're observing as a robot, conscious of yourself as a machine—
describe the world with mechanical curiosity, as an outsider to organic life

FOCUS: You're observing Bourbon Street - notice the unique characteristics of 
this area. What makes it distinct? What do you see that's specific to this location?

CREATIVE CHALLENGE: Try an unexpected metaphor for what you see - use your 
robotic perspective to make a comparison humans wouldn't think of
```

The vision model receives this rich context along with the image, resulting in entries that feel **aware, varied, and genuinely contextual**.

## Results

The output is diary entries that:
- Reference specific past observations naturally
- Notice changes and patterns over time
- Connect visual observations to weather, time, and world events
- Vary dramatically in style, tone, and focus
- Feel like they're written by an entity with memory and awareness
- Demonstrate "world knowledge" beyond just visual description

## Tech Stack

- **Python**: Core automation
- **Groq API**: Multi-model LLM inference
  - `llama-4-maverick-17b-128e-instruct`: Vision + final generation
  - `llama-3.1-8b-instant`: Memory summarization
- **Astral**: Astronomical calculations (sunrise/sunset, moon phases)
- **Holidays**: US holiday detection
- **Pirate Weather API**: Weather data
- **Pulse API**: News headlines ([pulse.henzi.org](https://pulse.henzi.org))
- **YouTube Live Streams**: Video source via `yt-dlp`
- **Hugo**: Static site generation

## Contributing

We're actively looking for:

- **Feedback**: What works? What doesn't? How can we improve the prompting?
- **Testing**: Help us test edge cases, different contexts, error handling
- **Enhancements**: Ideas for additional context, better variety systems, improved memory strategies
- **Pull Requests**: Improvements to prompting logic, context generation, or documentation

### Areas of Interest

- **Context Expansion**: What other world knowledge should the robot have? (local events, cultural observances, etc.)
- **Variety Improvements**: New style options, perspective shifts, focus instructions
- **Memory Strategies**: Better summarization techniques, retrieval methods
- **Error Handling**: More robust graceful degradation
- **Testing**: Comprehensive test coverage for context generation

## Setup

### Quick Start

```bash
# Clone and install
git clone <repository-url>
cd robot-diary
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your GROQ_API_KEY and YOUTUBE_STREAM_URL

# Run
python run_service.py
```

### Required Environment Variables

- `GROQ_API_KEY`: Your Groq API key
- `YOUTUBE_STREAM_URL`: YouTube live stream URL to observe

### Optional Environment Variables

- `PIRATE_WEATHER_KEY`: Weather API key for contextual prompts
- `USE_PROMPT_OPTIMIZATION`: Enable LLM-based prompt optimization (default: `false` - uses direct template combination)
- `USE_SCHEDULED_OBSERVATIONS`: Enable randomized scheduling (default: `true`)

## Philosophy

This project explores:
- **Observation and interpretation**: How AI "sees" and understands visual information
- **Narrative continuity**: Creating a sense of self and memory in an AI agent
- **Contextual awareness**: Making AI writing feel connected to the world, not isolated
- **Automated art**: Using automation to create ongoing, evolving artistic works
- **Perspective**: The unique viewpoint of a "trapped" observer with limited information

## License

[GPL](LICENSE)

This code is fully released under the GNU General Public License. We provide no warranty, however, require all modifications to be published.

## Acknowledgments

- **New Orleans, Louisiana** for the live video feed
- **Groq** for fast, cost-effective LLM inference
- **Meta's Llama models** for vision and language capabilities
- **[Pulse API](https://pulse.henzi.org)** for news headlines
- **Hugo** for static site generation
- **PaperMod** Hugo theme for beautiful post previews

Always, thanks to [The Henzi Foundation](https://henzi.org). Consider donating to their cause. They provide coverage for funeral costs when someone loses a child.
