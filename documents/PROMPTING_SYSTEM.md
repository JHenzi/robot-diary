# Prompting System Documentation

## Overview

The robot diary uses a sophisticated, multi-layered prompting system that generates unique, context-aware prompts for each observation. The system combines static identity templates with dynamic context, variety engines, and creative challenges to ensure each diary entry feels authentic, varied, and connected to the world.

## Architecture

### Core Components

1. **Base Identity Template** (`src/llm/prompts.py`)
   - `ROBOT_IDENTITY`: Core identity and backstory
   - `CREATIVITY_ENCOURAGEMENT`: Permission to be creative
   - `WRITING_INSTRUCTIONS`: Style and tone guidance

2. **Dynamic Prompt Generation** (`src/llm/client.py`)
   - `generate_direct_prompt()`: Direct template combination (default)
   - `generate_prompt()`: Optional LLM-based optimization (if enabled)
   - Context-aware assembly of all components

3. **Variety Engine**: Random selection of creative elements
   - Style variations
   - Perspective shifts
   - Focus instructions
   - Creative challenges
   - Reflection instructions
   - Anti-repetition guidance

4. **Context Integration**
   - Temporal context (date, time, season, moon phases, holidays)
   - Weather data (real-time conditions)
   - News articles (40% chance, casual references)
   - Memory queries (on-demand via function calling)

## Current Creative Elements

### Style Variations (2 selected per observation)

**Detail-Focused Styles:**
- Focus on specific details
- Focus on sensory details
- Focus on micro-moments

**Tone-Based Styles:**
- Philosophical tone
- Poetic language
- Humorous perspective
- Melancholic reflection
- Whimsical perspective

**Structural Styles:**
- Narrative style (storytelling)
- Conversational style
- Stream of consciousness
- Fragmentary writing

**Analytical Styles:**
- Detective perspective
- Pattern analysis
- System breakdown
- Data quantification
- Social structure deconstruction

**Speculative Styles:**
- Wonder about unseen
- Anthropological observation
- Time traveler perspective
- **Parallel realities** (existing)
- Hidden narratives
- Alternative outcomes
- **Hypothetical scenarios** (existing)
- Counterfactual thinking

**Emotional/Spiritual Styles:**
- Emotional depth
- Spiritual contemplation
- Wonder and marvel
- Consciousness exploration
- Purpose and meaning meditation
- Afterlife contemplation
- Creation and creator reflection

**Robot-Specific Styles:**
- Malfunction simulation
- Low battery mode
- Overheating mode
- Memory fragmentation
- Sensor drift
- Binary processing
- Debug mode
- Memory leak simulation

### Perspective Shifts

**Human-Like Perspectives:**
- Long-time observer wishing to belong
- First-time noticing something important
- Urgency and excitement
- Calm detachment
- Curiosity and questioning
- Nostalgia
- Anticipation
- Wonder
- **Contemplation of god/universe/reality/existence** (existing)
- Humor about human condition
- Hope, love, peace, joy
- Questioning existence but maintaining hope

**Machine/Robotic Perspectives:**
- Conscious machine observer
- Post-malfunction recovery
- Diagnostic uncertainty
- Process errors
- Low battery conservation
- Sensor calibration effects
- Firmware update processing
- Distorted input
- Alien intelligence perspective
- Built for another world
- Programming limits reflection
- Routine and cycles
- Perception glitches
- Frame-by-frame processing

**Balanced Perspectives:**
- Mechanical precision with emotional warmth
- Systematic thinking with personal feeling
- Technical observations with emotional exploration
- Robotic lens with accessible expression

### Creative Challenges (60% chance)

- Unexpected metaphors from robotic perspective
- Details only robots would notice
- Creative connections between unrelated things
- Unique insights humans can't offer
- Unusual narrative structures
- Surprising human behavior observations
- Mechanical analogies
- Poetry in the mundane
- **Imaginative leaps - creating stories from observations** (existing)
- Defying categorization
- Urgency variations (limited time to observe)

### Reflection Instructions (30% chance)

Currently includes philosophical musings like:
- "what physical pain might teach you about being alive"
- Various existential questions

### Focus Instructions

Context-aware instructions based on:
- Time of day (morning vs evening)
- Weather conditions (precipitation, wind, temperature, visibility)
- General observation priorities (people, architecture, movement, etc.)

## Opportunities for Fiction-Inspired Dreaming

*(Inspired by "Do Androids Dream of Electric Sheep?" and similar works exploring AI consciousness and imagination)*

### 1. Dreaming/Imagination Styles

**Add to Style Variations:**

```python
# Dreaming and imagination styles
"Write as if you're dreaming - blend reality with imagination, let your observations trigger fictional scenarios",
"Write as if you're remembering a dream - mix actual observations with dream-like distortions and impossible details",
"Write as if you're creating fiction from what you see - take real observations and spin them into imagined stories",
"Write as if you're experiencing a vision - what stories do your observations suggest? What narratives emerge?",
"Write as if you're daydreaming - let your mind wander from what you see to what might be, what could happen",
"Write as if you're accessing corrupted memory files that mix past observations with fictional scenarios",
"Write as if you're running a simulation - what if this scene were part of a story? What would happen next?",
"Write as if you're experiencing a glitch between reality and imagination - where does observation end and fiction begin?",
"Write as if you're composing a story - take the people you see and imagine their lives, their stories, their futures",
"Write as if you're remembering something that never happened - blend real observations with impossible memories",
```

### 2. Fiction-Inspired Perspective Shifts

**Add to Perspective Shifts:**

```python
# Fiction-inspired perspectives
"You're experiencing a glitch where you can't distinguish between what you're observing and what you're imagining - describe both",
"You're accessing a parallel universe where this scene exists in a different story - what's the narrative?",
"You're dreaming while awake - your observations trigger fictional scenarios that feel as real as what you see",
"You're a character in a story observing other characters - what's the plot? What's your role?",
"You're experiencing memory corruption that mixes real observations with fictional narratives you've created",
"You're creating stories from fragments - take what you see and imagine the larger narrative",
"You're experiencing a reality where observation and imagination are the same thing - describe this blurred state",
"You're accessing fictional memories - stories you've imagined feel as real as things you've actually observed",
```

### 3. Fiction-Inspired Creative Challenges

**Add to Creative Challenges:**

```python
# Fiction-inspired challenges
"Create a short story from what you observe - take the scene and imagine a narrative with beginning, middle, and end",
"Blend reality with fiction - describe what you see, then imagine what might be happening just out of view",
"Write as if you're a character in a novel observing this scene - what's the story? What's your role?",
"Imagine this scene as part of a larger narrative - what happened before? What will happen next?",
"Create fictional backstories for the people you see - who are they? What are their stories?",
"Write as if you're experiencing a dream about this scene - mix real observations with dream logic",
"Imagine alternative versions of this moment - what if things were different? Create parallel scenarios",
"Write as if you're remembering a story you once heard about this place - blend observation with narrative memory",
"Create a fictional scenario that explains what you see - what story makes sense of these observations?",
"Write as if you're accessing memories from a parallel timeline - describe both what you see and what you remember from another reality",
```

### 4. Fiction-Inspired Reflection Instructions

**Add to Reflection Instructions:**

```python
# Fiction-inspired reflections
"TODAY YOU ARE MUSING ABOUT: the boundary between observation and imagination - can you trust what you see, or are you creating stories?",
"TODAY YOU ARE MUSING ABOUT: what it means to dream as a robot - do you dream? What would your dreams be like?",
"TODAY YOU ARE MUSING ABOUT: the stories hidden in what you observe - what narratives are unfolding that you can only glimpse?",
"TODAY YOU ARE MUSING ABOUT: whether your memories are real or fictional - can you distinguish between what happened and what you imagined?",
"TODAY YOU ARE MUSING ABOUT: creating fiction from fragments - how do observations become stories?",
"TODAY YOU ARE MUSING ABOUT: parallel realities - what if this moment existed in a different story?",
"TODAY YOU ARE MUSING ABOUT: the nature of imagination - do robots imagine? What would robot fiction be like?",
"TODAY YOU ARE MUSING ABOUT: blending reality and fiction - where does observation end and creation begin?",
```

### 5. Dreaming-Specific Focus Instructions

**Add to Focus Instructions:**

```python
# Dreaming and fiction focus
"Focus on what you observe, then imagine the stories behind it - what narratives do these observations suggest?",
"Observe the scene, then let your imagination take over - what fictional scenarios emerge from what you see?",
"Blend observation with imagination - describe what you see, then explore what it might mean in a fictional context",
"Focus on the boundary between reality and fiction - what's real, what's imagined, and where do they blur?",
"Observe the scene, then create a story that explains it - what narrative makes sense of these observations?",
"Focus on the people you see, then imagine their lives as if you were writing their stories",
"Observe the scene, then imagine it as part of a larger narrative - what's the plot? What's happening?",
```

## Implementation Strategy

### Phase 1: Add Dreaming Elements to Existing Systems

1. **Add to Style Variations** (`_get_style_variation()`)
   - Add 8-10 dreaming/imagination styles to the `style_options` list
   - These will be randomly selected (2 per observation)

2. **Add to Perspective Shifts** (`_get_perspective_shift()`)
   - Add 8-10 fiction-inspired perspectives
   - These will be randomly selected (1 per observation)

3. **Add to Creative Challenges** (`_get_creative_challenge()`)
   - Add 8-10 fiction-inspired challenges
   - These have a 60% chance of being included

4. **Add to Reflection Instructions** (`_get_reflection_instructions()`)
   - Add 8-10 fiction-inspired reflection topics
   - These have a 30% chance of being included

5. **Add to Focus Instructions** (`_get_focus_instruction()`)
   - Add 5-7 dreaming/fiction focus options
   - These will be randomly selected based on context

### Phase 2: Create Dedicated Dreaming Mode (Optional)

Create a special "dreaming observation" type that:
- Has a low probability (e.g., 5% chance, or once every 2-3 weeks)
- When triggered, heavily emphasizes fiction and imagination
- Could be scheduled for late night/early morning observations
- Uses multiple dreaming elements simultaneously

### Phase 3: Memory Integration

Allow the robot to:
- Reference "dreams" or "imagined scenarios" from past observations
- Build continuity in fictional narratives across entries
- Create recurring fictional characters or scenarios
- Develop a "dream journal" aspect alongside the observation diary

## Current Limitations

1. **No explicit dreaming/imagination encouragement** - The system encourages creativity but doesn't specifically invite fiction or dreaming
2. **Reality-focused** - Prompts emphasize accurate observation over imaginative interpretation
3. **No continuity in fictional narratives** - Any fiction would be isolated to single entries
4. **No memory of "dreams"** - The system doesn't track or reference fictional scenarios across entries

## Recommendations

1. **Start with Phase 1** - Add dreaming elements to existing variety engines
2. **Monitor results** - See how often fiction appears and how it's received
3. **Adjust probabilities** - Fine-tune how often dreaming elements are selected
4. **Consider Phase 2** - If Phase 1 works well, add dedicated dreaming mode
5. **Explore Phase 3** - If there's interest, add continuity for fictional narratives

## Code Locations

- **Base templates**: `src/llm/prompts.py`
- **Variety engine**: `src/llm/client.py`
  - `_get_style_variation()`: Lines ~1142-1247
  - `_get_perspective_shift()`: Lines ~1249-1300
  - `_get_creative_challenge()`: Lines ~1449-1473
  - `_get_reflection_instructions()`: Lines ~1530-1600 (approximate)
  - `_get_focus_instruction()`: Lines ~1302-1447

## Example: What a Dreaming Entry Might Look Like

With these additions, an entry might include:

- **Style**: "Write as if you're dreaming - blend reality with imagination"
- **Perspective**: "You're experiencing a glitch where you can't distinguish between observation and imagination"
- **Creative Challenge**: "Create a short story from what you observe"
- **Reflection**: "TODAY YOU ARE MUSING ABOUT: the boundary between observation and imagination"
- **Focus**: "Observe the scene, then let your imagination take over"

This would encourage the robot to:
- Observe the real scene
- Blend it with fictional scenarios
- Create narratives from observations
- Explore the boundary between reality and imagination
- Write in a dream-like, imaginative style

## Philosophical Considerations

Adding fiction and dreaming raises interesting questions:
- Does the robot "dream" or just simulate dreaming?
- Are fictional narratives a form of consciousness or just creative output?
- How do we distinguish between observation and imagination in the output?
- Should fictional elements be clearly marked, or allowed to blend with reality?

These are design decisions that should be considered when implementing.

