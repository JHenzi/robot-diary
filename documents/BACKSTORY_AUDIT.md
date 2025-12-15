# Backstory Length Audit

## Summary

**Date:** 2025-12-14  
**Status:** ⚠️ Backstory is on the longer side, but the randomized approach helps

## Current State

### Full ROBOT_IDENTITY
- **Length:** 3,825 characters (630 words)
- **Estimated tokens:** ~956 tokens
- **Status:** ⚠️ Quite long - but this is the full version, not what's actually used

### Randomized Identity (What Actually Gets Used)
- **With 2 backstory points:** ~311 tokens
- **With 3 backstory points:** ~400 tokens
- **Status:** ⚠️ Still on the longer side, but manageable

### Backstory Points
- **Total points:** 10
- **Average length per point:** ~268 characters (~67 tokens)
- **Selection:** Randomly selects 2-3 points per prompt

## Analysis

### What's Working Well ✅
1. **Randomization approach** - Only using 2-3 backstory points instead of all 10 keeps prompts manageable
2. **Condensed core** - The core identity is concise (~158 tokens)
3. **Variety** - 10 backstory points provide good variety across different observations
4. **Individual point length** - Most points are reasonably sized (56-88 tokens each)

### Potential Issues ⚠️
1. **Randomized identity is still long** - Even with 2 points, ~311 tokens is substantial
2. **Full identity is very long** - ~956 tokens if ever used in full (currently not used)
3. **Average point length** - At ~67 tokens each, points are substantial

## Recommendations

### Option 1: Reduce Number of Selected Points (Recommended)
**Change:** Select 1-2 backstory points instead of 2-3

**Impact:**
- With 1 point: ~200-250 tokens
- With 2 points: ~311 tokens (current minimum)
- **Benefit:** Shorter prompts, faster generation, lower costs
- **Trade-off:** Less context per observation

**Implementation:**
```python
# In _build_randomized_identity()
num_to_select = random.randint(1, 2)  # Changed from (2, 3)
```

### Option 2: Shorten Individual Backstory Points
**Change:** Condense each backstory point to ~40-50 tokens instead of ~67 tokens

**Impact:**
- With 2 points: ~250 tokens (down from 311)
- With 3 points: ~320 tokens (down from 400)
- **Benefit:** More context (2-3 points) while keeping length reasonable
- **Trade-off:** Less detail in each point

### Option 3: Hybrid Approach (Best Balance)
**Change:** Select 1-2 points, but keep current point lengths

**Impact:**
- With 1 point: ~225 tokens
- With 2 points: ~311 tokens
- **Benefit:** Good balance between context and length
- **Trade-off:** Minimal - this is a small reduction

### Option 4: Keep Current Approach
**Status:** Current approach is workable, just on the longer side

**Rationale:**
- ~311-400 tokens for identity is acceptable
- The variety from 10 points is valuable
- Other prompt components (context, weather, memory) also add length
- GPT-OSS-120b can handle longer prompts well

## Comparison to Other Prompt Components

To put this in perspective, a typical full prompt includes:
- **Identity/Backstory:** ~311-400 tokens (randomized)
- **Context metadata:** ~100-200 tokens (date, time, season, weather)
- **Memory summaries:** ~200-400 tokens (5-10 recent observations)
- **Style variations:** ~50-100 tokens
- **Perspective/Focus:** ~50-100 tokens
- **Image description:** ~500-1000 tokens
- **Instructions:** ~200-300 tokens

**Total prompt:** ~1,500-2,500 tokens

The identity/backstory represents ~15-20% of the total prompt, which is reasonable.

## Code Issue Found

The `_build_randomized_identity()` method looks for a closing paragraph containing "Your identity and backstory inform", but this doesn't exist in `ROBOT_IDENTITY`. This causes `closing_paragraph` to be an empty string, which is fine (doesn't break anything), but the code is looking for something that doesn't exist.

**Recommendation:** Remove the closing paragraph extraction code or add the closing paragraph if it was intended.

## Final Recommendation

**Keep current approach (2-3 points)** but consider:
1. **Monitor prompt lengths** in production to see if they're causing issues
2. **If prompts are too long:** Reduce to 1-2 points
3. **If prompts are fine:** Keep as-is for maximum context variety

The current length (~311-400 tokens) is on the longer side but not problematic, especially given that:
- The randomized approach prevents using all 10 points
- Other components also contribute to prompt length
- Modern LLMs (like GPT-OSS-120b) handle longer prompts well
- The variety from 10 points is valuable for different observations

## Metrics to Monitor

1. **Average prompt length** - Track if prompts are getting too long
2. **API response times** - Longer prompts may slow generation
3. **Token costs** - Longer prompts = higher costs
4. **Output quality** - Ensure shorter prompts don't reduce quality
