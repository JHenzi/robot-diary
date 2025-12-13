# Architecture Decision Records

This document records important architectural decisions for the Robot Diary project.

## ADR-001: Use Groq with Llama-4-Maverick for Vision and Text Generation

**Date**: 2024-12-19  
**Status**: Accepted  
**Decision Makers**: Project Team

### Context

We need to select an LLM provider and model for:
1. **Vision capabilities**: Interpreting webcam images to describe what the robot "sees"
2. **Text generation**: Creating diary entries based on observations and memory
3. **Cost efficiency**: The system will run periodically, potentially generating many API calls
4. **Performance**: Fast response times for a smooth automated workflow

### Decision

We will use **Groq** as our LLM provider with the **`meta-llama/llama-4-maverick-17b-128e-instruct`** model.

### Rationale

1. **Cost Efficiency**: Groq offers competitive pricing, which is important for a project that will make frequent API calls over time
2. **Vision Capabilities**: The `llama-4-maverick-17b-128e-instruct` model supports vision tasks, allowing us to process images directly
3. **Performance**: Groq's infrastructure is optimized for fast inference, providing low latency responses
4. **Model Quality**: Llama-4-Maverick is a capable model for both vision understanding and creative text generation
5. **Unified Model**: Using a single model for both vision and text generation simplifies the architecture and reduces complexity

### Consequences

#### Positive
- Lower operational costs compared to OpenAI GPT-4 Vision
- Fast inference times
- Single model for both vision and text tasks
- Good balance of capability and cost

#### Negative
- Model may have different quality/characteristics compared to GPT-4
- Need to adapt prompts for Llama model behavior
- Groq API may have different rate limits or constraints than OpenAI

#### Neutral
- Requires Groq API key setup
- May need to adjust prompt engineering for optimal results with Llama

### Implementation Notes

- Use `groq` Python SDK for API integration
- Model identifier: `meta-llama/llama-4-maverick-17b-128e-instruct`
- Store `GROQ_API_KEY` in environment variables
- Implement proper error handling for Groq API responses
- Test vision capabilities with sample images before full deployment

### Alternatives Considered

1. **OpenAI GPT-4 Vision + GPT-4 Turbo**
   - Pros: High quality, well-documented, proven performance
   - Cons: Higher cost, requires separate models for vision and text
   - Rejected due to cost concerns for long-term operation

2. **Claude (Anthropic)**
   - Pros: High quality, good vision capabilities
   - Cons: Higher cost, may require separate models
   - Rejected due to cost and complexity

3. **Local Models (Ollama, etc.)**
   - Pros: No API costs, full control
   - Cons: Requires significant infrastructure, setup complexity
   - Rejected due to infrastructure requirements

### References

- Groq API Documentation: https://console.groq.com/docs
- Model: `meta-llama/llama-4-maverick-17b-128e-instruct`
- Groq Python SDK: https://github.com/groq/groq-python

---

## ADR-002: Service-Based Architecture with Dynamic Prompt Generation

**Date**: 2024-12-19  
**Status**: Accepted  
**Decision Makers**: Project Team

### Context

We need to decide on the execution model for the robot diary system:
1. **Execution Model**: Should the system run on a schedule (cron) or as a continuous service?
2. **Hugo Integration**: The Hugo site is located in the `hugo/` folder and needs to be built when new content is generated
3. **Prompt Engineering**: Prompts must be dynamic and consider recent history to create narrative continuity
4. **Cost Optimization**: We want to optimize API costs while maintaining quality

### Decision

We will implement a **service-based architecture** that:
1. Runs continuously in the background as a long-running service
2. Automatically builds Hugo when new content is generated
3. Uses a **two-model approach** for prompt generation:
   - **Cheaper model** (`openai/gpt-oss-20b` via Groq) for dynamic prompt generation based on recent history
   - **Primary model** (`meta-llama/llama-4-maverick-17b-128e-instruct`) for final vision interpretation and diary entry generation

### Rationale

1. **Service Architecture**:
   - Allows real-time response to new observations
   - Simplifies Hugo build integration (build on content update)
   - Better for monitoring and error recovery
   - More suitable for an "art piece" that should feel alive and responsive

2. **Dynamic Prompt Generation**:
   - Recent history is crucial for narrative continuity
   - Prompts need to adapt based on what the robot has recently observed
   - Two-model approach allows cost-effective prompt optimization

3. **Two-Model Approach**:
   - Cheaper model (`gpt-oss-20b`) analyzes recent memory and generates optimized prompts
   - Primary model (`llama-4-maverick`) uses optimized prompts for final generation
   - Reduces costs while maintaining quality
   - Allows for sophisticated prompt engineering without expensive iterations

### Consequences

#### Positive
- Real-time content generation and publishing
- Automatic Hugo builds on content updates
- Cost-effective prompt optimization
- Better narrative continuity through dynamic prompts
- Easier to monitor and maintain as a service

#### Negative
- Requires service management (systemd, supervisor, etc.)
- More complex than simple scheduled scripts
- Need to handle service restarts and error recovery
- Two API calls per cycle (prompt generation + final generation)

#### Neutral
- Service can be configured with observation frequency
- Hugo builds happen automatically but can be configured
- Memory system becomes more critical for prompt generation

### Implementation Notes

- Service should run as a background daemon/service
- Observation frequency configurable (e.g., every N hours)
- Hugo build triggered automatically after new post generation
- Prompt generation flow:
  1. Load recent memory/history
  2. Use `openai/gpt-oss-20b` to analyze history and generate optimized prompt
  3. Use optimized prompt with `llama-4-maverick` for vision + diary generation
- Service should handle:
  - Graceful shutdown
  - Error recovery
  - Logging
  - Health checks

### Alternatives Considered

1. **Scheduled Execution (Cron)**
   - Pros: Simple, well-understood, no service management
   - Cons: Requires separate Hugo build process, less responsive, harder to integrate builds
   - Rejected in favor of service architecture for better integration

2. **Single Model Approach**
   - Pros: Simpler, fewer API calls
   - Cons: Less sophisticated prompt engineering, higher costs for prompt iteration
   - Rejected in favor of two-model approach for cost-effective prompt optimization

3. **Manual Prompt Templates**
   - Pros: Simple, predictable
   - Cons: Less dynamic, doesn't adapt to recent history effectively
   - Rejected in favor of dynamic prompt generation

### References

- Groq Model: `openai/gpt-oss-20b` (for prompt generation)
- Groq Model: `meta-llama/llama-4-maverick-17b-128e-instruct` (for final generation)
- Hugo site located in `hugo/` directory

---

## ADR-003: Enhanced Dynamic Prompting with Date/Time and Weather Context

**Date**: 2024-12-19  
**Status**: Proposed  
**Decision Makers**: Project Team

### Context

The current dynamic prompting system uses recent memory to generate context-aware prompts, but lacks:
1. **Temporal awareness**: No current date/time context
2. **Weather context**: No weather information for Cincinnati
3. **Time-of-day awareness**: Robot doesn't know if it's morning, evening, etc.
4. **Seasonal context**: No awareness of season or time of year

These limitations reduce the robot's ability to make time-sensitive observations and weather-related correlations.

### Decision

We will enhance the dynamic prompting system to include:
1. **Date/Time Context**: Current date, time, day of week, season
2. **Weather Integration**: Fetch and include current weather for Cincinnati
3. **Enhanced Prompt Generation**: Combine temporal + weather + memory context

### Rationale

1. **Temporal Awareness**:
   - Allows robot to reference specific dates and times
   - Enables time-of-day specific observations (morning vs evening)
   - Provides seasonal context (winter vs summer)
   - Creates more authentic diary entries

2. **Weather Context**:
   - Enables weather-visual correlations
   - Robot can comment on weather conditions
   - Notices weather-related changes (wet streets, people with umbrellas)
   - Adds realism to observations

3. **Enhanced Narrative**:
   - More contextually rich diary entries
   - Better narrative continuity
   - More engaging and authentic robot perspective

### Implementation Plan

#### Phase 1: Date/Time Integration
- Add datetime context to prompt generation
- Format: "Today is {day}, {date} at {time}"
- Include: Day of week, date, time, season
- Timezone: Cincinnati timezone (America/New_York)

#### Phase 2: Weather Integration
- Select weather API (recommend Weather.gov - free, no key)
- Implement weather fetching module
- Cache weather data (15-30 minute TTL)
- Integrate weather into prompt generation

#### Phase 3: Enhanced Prompt Generation
- Update prompt generation to include:
  - Date/time context
  - Weather data
  - Recent memory
  - Base template
- Generate prompts that reference all context sources

### Consequences

#### Positive
- More contextually aware diary entries
- Time-sensitive observations
- Weather-visual correlations
- Enhanced narrative quality
- More authentic robot perspective

#### Negative
- Additional API call for weather (if using paid service)
- Slightly more complex prompt generation
- Need to manage weather API rate limits
- Weather cache management

#### Neutral
- Weather.gov is free (no API key needed)
- Minimal performance impact
- Can be disabled via configuration

### Alternatives Considered

1. **No Weather Integration**
   - Pros: Simpler, fewer API calls
   - Cons: Less context, missed opportunities for weather observations
   - Rejected: Weather adds significant value to narrative

2. **Paid Weather API (OpenWeatherMap)**
   - Pros: More features, reliable
   - Cons: API key needed, potential costs
   - Rejected in favor of free Weather.gov API

3. **Manual Date/Time Entry**
   - Pros: No implementation needed
   - Cons: Not dynamic, requires manual updates
   - Rejected: System should be fully automated

### References

- Weather.gov API: https://www.weather.gov/documentation/services-web-api
- Python datetime: https://docs.python.org/3/library/datetime.html
- See WORKFLOW_DOCUMENTATION.md for detailed implementation plan

