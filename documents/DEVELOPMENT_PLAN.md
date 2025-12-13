# Robot Diary - Development Plan

This document outlines the development roadmap for the Robot Diary art project.

## Project Overview

**Goal**: Create an autonomous system that periodically observes downtown Cincinnati through a webcam, interprets the view using AI, and publishes diary entries as blog posts.

**Current Status**: Basic image fetching from Windy API is implemented (`test.py`)

## Development Phases

### Phase 1: Core Infrastructure ✅ (Partially Complete)

**Status**: In Progress  
**Goal**: Set up basic project structure and image fetching

#### Tasks:
- [x] Windy API integration for fetching webcam images
- [ ] Project structure setup (src/, content/, images/, memory/)
- [ ] Environment variable management
- [ ] Requirements.txt with dependencies
- [ ] Basic error handling and logging

**Deliverables**:
- Working image download from Windy API
- Proper project structure
- Configuration system

---

### Phase 2: LLM Integration

**Status**: Not Started  
**Goal**: Integrate Groq API with two-model approach for dynamic prompts and diary generation

#### Tasks:
- [ ] Groq API client setup
- [ ] Prompt generation model integration
  - Use `openai/gpt-oss-20b` for dynamic prompt generation
  - Analyze recent memory/history
  - Generate context-aware prompts
- [ ] Image-to-text vision API integration
  - Send image to `meta-llama/llama-4-maverick-17b-128e-instruct`
  - Extract description of what the robot "sees"
- [ ] Text generation for diary entries
  - Use optimized prompts from prompt generator
  - Implement robot persona/perspective
  - Generate narrative diary entries
- [ ] Error handling for API rate limits and failures

**Deliverables**:
- Function to generate dynamic prompts using `gpt-oss-20b`
- Function to get image description from Groq/Llama Vision
- Function to generate diary entry text using optimized prompts
- Basic prompt templates and prompt generation logic

**Dependencies**: Phase 1, Phase 3 (memory needed for prompt generation)

**Note**: See [DECISIONS.md](DECISIONS.md) ADR-001 and ADR-002 for rationale on model selection and two-model approach

---

### Phase 3: Memory System

**Status**: Not Started  
**Goal**: Implement context storage so the robot remembers past observations

#### Tasks:
- [ ] Design memory storage format (JSON file or simple database)
- [ ] Implement memory storage/retrieval functions
- [ ] Create memory summarization (condense old memories)
- [ ] Memory query functions for prompt generation
  - Get recent observations (last N entries)
  - Get thematic memories (by topic/pattern)
  - Format memory for prompt generator input
- [ ] Integrate memory into LLM prompts
  - Include recent observations in prompt generation
  - Allow robot to reference past events in diary entries
- [ ] Memory retention policy (how long to keep memories)

**Deliverables**:
- Memory storage system
- Functions to save/load/query memories
- Memory formatting for prompt generation
- Memory integration in diary generation

**Dependencies**: None (can be developed in parallel with Phase 2)

**Note**: Memory system is critical for Phase 2's prompt generation step

---

### Phase 4: Hugo Integration

**Status**: Not Started  
**Goal**: Generate Hugo blog posts from diary entries and automatically build the site

#### Tasks:
- [ ] Hugo post template creation
  - Front matter (title, date, tags, etc.)
  - Markdown content structure
- [ ] Post generation function
  - Create markdown file with proper front matter
  - Save to `hugo/content/posts/` directory
- [ ] Image handling
  - Copy images to `hugo/static/images/` directory
  - Reference images in posts
- [ ] Post metadata
  - Timestamps
  - Tags/categories
  - Permalinks
- [ ] Automatic Hugo build integration
  - Trigger Hugo build after post generation
  - Handle build errors gracefully
  - Optional: auto-deploy built site

**Deliverables**:
- Function to generate Hugo post from diary entry
- Template for post structure
- Image management system
- Automatic Hugo build on content updates

**Dependencies**: Phase 2

---

### Phase 5: Service Architecture & Orchestration

**Status**: Not Started  
**Goal**: Create long-running service that orchestrates the complete pipeline

#### Tasks:
- [ ] Service daemon implementation (`src/service.py`)
  - Long-running background service
  - Configurable observation intervals
  - Complete observation cycle:
    - Fetch image
    - Load recent memory
    - Generate dynamic prompt (using `gpt-oss-20b`)
    - Get LLM vision interpretation (using `llama-4-maverick`)
    - Generate diary entry with optimized prompt
    - Save memory
    - Generate Hugo post
    - Trigger Hugo build
- [ ] Service management
  - Graceful shutdown handling
  - Signal handling (SIGTERM, SIGINT)
  - Health check endpoints (optional)
- [ ] Error handling and recovery
  - Retry logic for API failures
  - Service restart on critical errors
  - Error logging and alerting
- [ ] Logging system
  - Structured logging
  - Log rotation
  - Observation cycle logging
- [ ] Configuration management
  - Environment variable configuration
  - Observation interval configuration
  - Service configuration file (optional)

**Deliverables**:
- Complete service daemon
- Service management and lifecycle
- Error handling and logging
- Documentation for running as system service

**Dependencies**: Phases 2, 3, 4

**Note**: See [DECISIONS.md](DECISIONS.md) ADR-002 for rationale on service-based architecture

---

### Phase 6: Enhancement & Polish

**Status**: Not Started  
**Goal**: Improve quality and add advanced features

#### Tasks:
- [ ] **Date/Time Context Integration** (High Priority)
  - Add current date/time to prompt generation
  - Include day of week, season, time of day
  - Configure timezone (Cincinnati: America/New_York)
  - Update prompt templates to use temporal context
- [ ] **Weather Integration** (High Priority)
  - Research and select weather API (Weather.gov recommended)
  - Implement weather fetching module
  - Add weather caching (15-30 min TTL)
  - Integrate weather into prompt generation
  - Add weather data to memory/observations
- [ ] Prompt engineering improvements
  - Better robot persona in prompt templates
  - More engaging narrative style
  - Improve prompt generation logic with date/weather context
  - Fine-tune prompt generator prompts
- [ ] Memory improvements
  - Better summarization
  - Thematic memory organization
  - Long-term vs short-term memory
- [ ] Post quality improvements
  - Better formatting
  - Image captions
  - Cross-references to past entries
- [ ] Monitoring and analytics
  - Track generation success/failure
  - Monitor API usage
  - Post statistics

**Deliverables**:
- Enhanced narrative quality with temporal awareness
- Weather-aware observations
- Improved memory system
- Better post formatting

**Dependencies**: Phase 5

**Note**: See [WORKFLOW_DOCUMENTATION.md](WORKFLOW_DOCUMENTATION.md) for detailed requirements and [DECISIONS.md](DECISIONS.md) ADR-003 for rationale

---

### Phase 7: Expansion Features

**Status**: Not Started  
**Goal**: Add additional activities beyond image observation

#### Tasks:
- [ ] News reading integration
  - Fetch relevant news articles
  - Summarize for robot
  - Generate diary entries about news
- [ ] Weather integration
  - Fetch weather data
  - Correlate with observations
  - Include in diary entries
- [ ] Time-based activities
  - Different activities at different times
  - Special entries for events/holidays
- [ ] Multi-modal observations
  - Combine image + weather + news in single entries

**Deliverables**:
- News reading functionality
- Weather integration
- Expanded activity system

**Dependencies**: Phase 6

---

## Technical Considerations

### API Rate Limits
- **Windy API**: Check rate limits and implement caching if needed
- **Groq API**: 
  - Check rate limits for both models (`gpt-oss-20b` and `llama-4-maverick`)
  - Two API calls per observation cycle (prompt generation + final generation)
  - Implement retry logic with exponential backoff
  - Consider caching similar images to reduce API calls
  - Monitor usage for cost optimization

### Storage
- **Images**: May accumulate over time - implement cleanup policy
- **Memory**: Will grow - need summarization/archival strategy
- **Posts**: Hugo will handle, but consider backup strategy

### Error Handling
- Network failures (API unavailable)
- Invalid API responses
- Image download failures
- LLM API errors
- Hugo build failures

### Cost Management
- Monitor Groq API usage (vision + text generation with Llama-4-Maverick)
- Consider image caching to avoid redundant API calls
- Implement usage tracking
- Groq chosen for cost efficiency (see DECISIONS.md)

## Testing Strategy

### Unit Tests
- Image fetching functions
- Memory storage/retrieval
- Post generation
- Prompt building

### Integration Tests
- Full pipeline test (image → LLM → post)
- Error recovery scenarios
- Memory persistence

### Manual Testing
- Run full cycle and verify output
- Check Hugo site builds correctly
- Verify published posts

## Deployment Considerations

### Local Development
- Run manually for testing
- Use local Hugo site for preview

### Production
- Run as systemd service or similar daemon
- Automated Hugo build on content updates
- Monitoring and alerting
- Backup strategy for memory and content
- Service health monitoring

## Timeline Estimate

- **Phase 1**: 1-2 days
- **Phase 2**: 2-3 days
- **Phase 3**: 2-3 days
- **Phase 4**: 1-2 days
- **Phase 5**: 1-2 days
- **Phase 6**: 3-5 days (ongoing)
- **Phase 7**: 5-7 days (future expansion)

**Total MVP (Phases 1-5)**: ~7-12 days  
**Full Featured (Phases 1-6)**: ~10-17 days  
**With Expansions (All phases)**: ~15-24 days

## Next Steps

1. **Immediate**: Complete Phase 1 - set up proper project structure
2. **Short-term**: Implement Phase 2 - LLM integration
3. **Medium-term**: Complete Phases 3-5 for MVP
4. **Long-term**: Enhancements and expansions

## Notes

- Start simple, iterate based on results
- The "robot persona" will evolve as we see what works
- Prompt engineering is crucial for narrative quality
- Memory system design affects narrative continuity
- Consider the artistic/creative goals alongside technical implementation

