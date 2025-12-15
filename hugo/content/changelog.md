---
title: "Prompting Changelog"
date: 2025-12-14
description: "A history of how we've enhanced the prompting system to create better, more varied, and more coherent diary entries. This changelog tracks the evolution from simple prompts to sophisticated prompt chaining with GPT-OSS-120b."
draft: false
---

## Overview

This changelog documents the evolution of our prompting system—from simple static prompts to sophisticated prompt chaining that produces richer, more varied, and more coherent diary entries. The journey has been one of continuous refinement, with each iteration building on lessons learned from the robot's actual output.

## December 14, 2025: The GPT-OSS-120b Revolution

### Prompt Chaining: A Two-Step Process

**Commit: `dff7b4f` - "4real"**  
**Commit: `86b4cd2` - "So much better"**

The most significant improvement to date: we introduced **prompt chaining**—a two-step process that separates factual image description from creative writing.

#### The Problem
Previously, we sent images directly to the vision model and asked it to both describe what it saw AND write creatively about it in a single step. This led to:
- Hallucinations and made-up details
- Inconsistent grounding in the actual image
- Difficulty maintaining the robot's voice while accurately describing the scene

#### The Solution: Two-Step Prompt Chaining

**Step 1: Factual Image Description** (`describe_image()`)
- Uses `meta-llama/llama-4-maverick-17b-128e-instruct` (vision model)
- Very low temperature (0.1) for factual accuracy
- Focused prompt: "Describe ONLY what you can clearly see"
- Produces a detailed, factual description of the image contents

**Step 2: Creative Diary Writing** (`create_diary_entry()`)
- Uses `openai/gpt-oss-120b` (configurable via `DIARY_WRITING_MODEL`)
- Higher temperature (0.5-0.85) for creativity
- Receives the factual description as input
- Writes the creative diary entry grounded in the description

#### Why This Works So Much Better

1. **Separation of Concerns**: Vision model does what it's best at (seeing), writing model does what it's best at (creating narrative)
2. **Better Grounding**: The writing model can only work with what's actually in the description, reducing hallucinations
3. **Model Specialization**: GPT-OSS-120b is much better at creative writing and maintaining narrative voice than smaller vision models
4. **Quality Improvement**: Stories became significantly more coherent, creative, and engaging

#### Configuration

```python
# config.py
DIARY_WRITING_MODEL = os.getenv('DIARY_WRITING_MODEL', VISION_MODEL)
# Can be set to 'openai/gpt-oss-120b' for better creative writing
```

The system now defaults to using GPT-OSS-120b for diary writing when configured, while still using the vision model for the initial factual description.

---

## December 13, 2025: Enhanced Prompting & Personality Drift

### Enhanced Prompting (No Preprompting)

**Commit: `dfbd1ba` - "Enhanced Prompting-No Preprompting"**  
**Commit: `0cebe09` - "Enhanced Prompting"**

We moved from LLM-based prompt optimization to **direct template combination** for better context preservation and lower latency.

#### Key Changes:
- **Direct Prompt Generation**: Bypassed intermediate LLM optimization step
- **Template Combination**: Intelligently combines prompt components based on context
- **Context Preservation**: All context information is preserved in the final prompt
- **Reduced Latency**: Eliminated the extra API call for prompt optimization

#### Personality Drift Enhancement

**Commit: `bd26772` - "Enhancing Personality Drift"**

Expanded personality evolution system with:
- **Event-driven modifiers**: Personality changes based on seasons, holidays, weather patterns
- **Milestone tracking**: Personality shifts at key observation counts (5, 15, 30, 60, 100, 200+)
- **Long-term perspective**: Personality evolves based on days since first observation
- **Contextual moods**: Winter introspection, spring optimism, summer energy, fall nostalgia

The robot's personality now evolves more naturally over time, responding to both accumulated experience and current context.

---

## December 12, 2025: Randomization for Variety

**Commits: `922e42c`, `2a8315a`, `0e36315`, `e604458`, `cd59fe0` - "Randomizing Prompting For Variety"**

Introduced a comprehensive **variety engine** to prevent repetitive entries:

### Style Variations
- 50+ different writing styles (narrative, analytical, philosophical, poetic, etc.)
- Random selection of 2 styles per entry
- Robot-specific styles (malfunction modes, sensor drift, debug mode, etc.)

### Perspective Shifts
- 30+ different perspectives (curiosity, nostalgia, urgency, wonder, etc.)
- Balanced robotic-personable perspectives
- Machine-specific perspectives (firmware updates, battery low, etc.)

### Focus Instructions
- Time-based focuses (morning vs. evening)
- Weather-based focuses (rain, wind, temperature)
- Location-specific focuses (Bourbon Street, New Orleans)
- General focuses (people, architecture, movement, patterns)

### Creative Challenges
- 60% chance of including a creative challenge
- Encourages unexpected angles and surprising connections
- Prompts innovation and unique robotic insights

### Anti-Repetition System
- Analyzes recent entry openings for patterns
- Provides explicit instructions to avoid repetition
- Encourages finding new ways to express observations

---

## Early Development: Foundation

**Commits: `ce56ee9` - "Stupidly, I'm messing with the prompts"**  
**Commits: `9d6511d`, `6225a45` - "We are going live"**

The initial prompting system established:
- Base robot identity and backstory
- Core writing instructions
- Basic context awareness (date, time, weather)
- Memory integration for narrative continuity

---

## Technical Evolution Summary

### Models Used Over Time

1. **Initial**: Single vision model for both description and writing
2. **Enhanced**: Separate models for different tasks
   - Prompt generation: `openai/gpt-oss-20b` (optional)
   - Vision: `meta-llama/llama-4-maverick-17b-128e-instruct`
   - Writing: `openai/gpt-oss-120b` (configurable)
   - Memory summarization: `llama-3.1-8b-instant`

### Prompt Architecture Evolution

1. **Static Prompts** → Simple template with basic context
2. **LLM-Optimized Prompts** → Intermediate model optimizes prompt (optional)
3. **Direct Template Combination** → Intelligent component assembly (current default)
4. **Prompt Chaining** → Two-step process: describe then write (current)

### Key Metrics

- **Prompt Components**: From 3-4 basic sections to 10+ dynamic components
- **Variety Options**: From 0 to 50+ style variations, 30+ perspectives
- **Context Awareness**: From basic date/weather to full temporal, seasonal, and event awareness
- **Model Specialization**: From 1 model to 4 specialized models
- **Quality**: Significant improvement in coherence, creativity, and grounding

---

## Current State (December 14, 2025)

The prompting system now features:

✅ **Prompt Chaining**: Two-step process for better grounding and creativity  
✅ **GPT-OSS-120b**: Large model for creative writing quality  
✅ **Direct Template Combination**: Fast, context-preserving prompt generation  
✅ **Comprehensive Variety Engine**: 50+ styles, 30+ perspectives, dynamic focuses  
✅ **Personality Drift**: Event-driven evolution based on experience and context  
✅ **Rich Context Integration**: Temporal, seasonal, weather, news, memory  
✅ **Anti-Repetition System**: Explicit guidance to avoid patterns  
✅ **Model Specialization**: Right model for each task  

The result: diary entries that are more varied, more grounded, more creative, and more coherent—while maintaining the robot's unique voice and perspective.

---

## Future Enhancements

Potential areas for further improvement:

- **Multi-turn refinement**: Allow the writing model to refine its output
- **Style consistency**: Track and maintain style preferences over time
- **Thematic continuity**: Better tracking of recurring themes and motifs
- **Interactive elements**: Allow the robot to "remember" reader feedback
- **Advanced memory**: More sophisticated memory retrieval and integration

---

*This changelog is maintained as the prompting system evolves. Each entry represents a significant improvement in the quality, variety, or coherence of the robot's diary entries.*
