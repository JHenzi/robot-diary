# Metadata Discussion: What Context Should B3N-T5-MNT Have?

This document discusses the metadata and context information we're providing to B3N-T5-MNT's prompt generation system, and explores what additional metadata might be interesting to include.

## Currently Implemented Metadata

### 1. Date and Time Context ✅

**What we're including:**
- Full date: "December 11, 2025"
- Time: "10:51 PM EST"
- Day of week: "Wednesday"
- Month name: "December"
- Season: "Winter"
- Time of day: "evening", "morning", "afternoon", "night"
- Weekend vs weekday: Boolean flags

**Why it's useful:**
- Robot can reference specific dates in diary entries
- Time-aware observations (morning light vs evening darkness)
- Seasonal context (winter cold vs summer heat)
- Day-specific patterns (weekend crowds vs weekday rush hours)
- Creates temporal continuity in the narrative

**Example prompt usage:**
> "Today is Wednesday, December 11, 2025 at 10:51 PM EST. It is Winter (evening). It is a weekday."

### 2. Weather Context ✅

**What we're including (from Pirate Weather API):**
- Temperature (actual and "feels like")
- Weather summary/conditions
- Wind speed and gusts (especially if windy)
- Precipitation probability and type
- Humidity
- Cloud cover
- Visibility
- UV index

**Why it's useful:**
- Robot can comment on weather conditions
- Correlate visual observations with weather (wet streets, people with umbrellas)
- Notice weather-related changes (snow, rain, wind)
- Seasonal weather patterns
- Creates more realistic and contextually aware observations

**Example prompt usage:**
> "The weather is Breezy and Mostly Clear with a temperature of 42°F. it's very windy with speeds of 17 mph and gusts up to 25 mph."

**Special handling:**
- Highlights windy conditions (>15 mph) for more interesting prompts
- Emphasizes precipitation when probability >30%
- Caches weather data for 30 minutes to reduce API calls

## Interesting Metadata to Consider Adding

### 3. Sunrise/Sunset Times 🌅

**What it would provide:**
- Time until/since sunrise
- Time until/since sunset
- Whether it's currently day or night
- Length of day

**Why it's interesting:**
- Robot can reference "the sun is setting" or "dawn is approaching"
- Creates awareness of natural light cycles
- Can notice if observations happen at unusual times (late night, early morning)
- Adds poetic/reflective quality to entries

**Implementation:**
- Available from Pirate Weather API `daily` forecast (sunriseTime, sunsetTime)
- Could also use a simple calculation library

**Example:**
> "The sun set 2 hours ago. The city is now in darkness, lit only by streetlights and building windows."

### 4. Moon Phase 🌙

**What it would provide:**
- Current moon phase (new, waxing, full, waning)
- Moon visibility
- Moonrise/moonset times

**Why it's interesting:**
- Adds another natural cycle to observe
- Full moon might affect lighting in night observations
- Creates another temporal marker for the robot
- Adds variety to night-time observations

**Implementation:**
- Available from Pirate Weather API `daily` forecast (moonPhase)
- Could calculate from date

**Example:**
> "A waxing gibbous moon hangs in the sky, casting a pale light over the city."

### 5. Holiday/Event Awareness 🎉

**What it would provide:**
- Major holidays (Christmas, New Year, Independence Day, etc.)
- Local Cincinnati events (if available)
- Day of year (e.g., "day 345 of the year")

**Why it's interesting:**
- Robot can notice holiday decorations, increased activity
- Creates awareness of special days
- Adds context for unusual patterns (holiday traffic, celebrations)
- Makes entries more time-aware

**Implementation:**
- Could use a holidays library (e.g., `holidays` Python package)
- Or maintain a simple list of major holidays
- Could integrate with local event calendars (future enhancement)

**Example:**
> "It's December 25th - Christmas Day. The streets are unusually quiet, most people likely at home with their families."

### 6. Time Since Last Observation ⏱️

**What it would provide:**
- Hours/days since last diary entry
- Number of observations made
- Pattern of observation frequency

**Why it's interesting:**
- Robot can reference "it's been 6 hours since my last observation"
- Creates sense of time passing
- Can notice if observations are irregular
- Adds continuity between entries

**Implementation:**
- Already have this in memory system
- Just need to format it for prompts

**Example:**
> "Six hours have passed since my last observation. The city has transitioned from afternoon to evening."

### 7. Weather Trends 📈

**What it would provide:**
- Temperature change since last observation
- Weather pattern changes (sunny → rainy)
- Seasonal trends

**Why it's interesting:**
- Robot can notice "it's gotten colder" or "the weather has changed"
- Creates awareness of change over time
- More dynamic than just current conditions
- Adds narrative depth

**Implementation:**
- Compare current weather with weather from previous observation (stored in memory)
- Calculate trends (warming, cooling, etc.)

**Example:**
> "The temperature has dropped 10 degrees since my last observation. Winter's grip is tightening."

### 8. Day of Year / Progress Through Season 📅

**What it would provide:**
- Day number of the year (1-365/366)
- Progress through current season (early/mid/late)
- Days until next season

**Why it's interesting:**
- Robot can reference "we're deep into winter" or "spring is approaching"
- Creates sense of seasonal progression
- Adds temporal awareness beyond just current date

**Implementation:**
- Simple calculation from date
- Could categorize: early (first third), mid (middle third), late (final third) of season

**Example:**
> "We're in the middle of winter, with spring still weeks away. The days are short, the nights long."

### 9. Light Conditions 💡

**What it would provide:**
- Estimated natural light level (based on time, weather, season)
- Whether streetlights would be on
- Visibility conditions

**Why it's interesting:**
- Robot can comment on lighting quality
- Correlates with what it can actually see
- Adds realism to observations
- Can notice if visibility is poor due to weather

**Implementation:**
- Calculate from time of day, sunrise/sunset, cloud cover
- Could use weather visibility data

**Example:**
> "The heavy cloud cover and late hour mean the city is dimly lit. My sensors struggle to make out details in the distance."

### 10. Human Activity Patterns 👥

**What it would provide:**
- Expected activity level (rush hour, lunch time, quiet hours)
- Typical patterns for this day/time
- Whether current activity matches expectations

**Why it's interesting:**
- Robot can notice "unusually quiet" or "more people than usual"
- Creates awareness of normal vs abnormal patterns
- Adds social context
- Makes observations more meaningful

**Implementation:**
- Heuristic based on time of day and day of week
- Could learn from past observations (future ML enhancement)

**Example:**
> "It's 2 PM on a Wednesday - typically a quiet time. But today the streets are unusually busy. Something is different."

## Priority Recommendations

### High Priority (Easy to implement, high value):
1. ✅ **Date/Time** - Already implemented
2. ✅ **Weather** - Already implemented
3. **Sunrise/Sunset** - Available from weather API, adds natural light awareness
4. **Time Since Last Observation** - Easy, adds continuity

### Medium Priority (Moderate effort, good value):
5. **Moon Phase** - Available from weather API, adds variety
6. **Weather Trends** - Compare with previous observation
7. **Day of Year / Season Progress** - Simple calculation, adds temporal depth

### Low Priority (Future enhancements):
8. **Holiday Awareness** - Requires holiday library or manual list
9. **Light Conditions** - Calculation based on other data
10. **Human Activity Patterns** - Heuristic or ML-based

## Implementation Notes

### Weather API Usage
- Pirate Weather API provides: `sunriseTime`, `sunsetTime`, `moonPhase` in daily forecast
- Need to request `daily` block (currently excluding it for efficiency)
- Could fetch daily forecast once per day, cache for 24 hours

### Caching Strategy
- Weather: 30 minutes (current)
- Sunrise/sunset: 24 hours (changes daily)
- Moon phase: 24 hours (changes slowly)
- Holidays: Calculate on demand (no API needed)

### Prompt Length Considerations
- More metadata = longer prompts
- Need to balance context richness with token limits
- Current approach: Include all metadata, let prompt generator decide what's relevant

## Example Enhanced Context String

With all recommended metadata:

```
Current Context:
Today is Wednesday, December 11, 2025 at 10:51 PM EST. It is Winter (evening). It is a weekday. 
The sun set 3 hours ago. A waxing gibbous moon is visible. We're in the middle of winter, 
with spring still 10 weeks away. Six hours have passed since my last observation.

Weather Conditions:
The weather is Breezy and Mostly Clear with a temperature of 42°F. it's very windy with speeds 
of 17 mph and gusts up to 25 mph. The temperature has dropped 5 degrees since my last observation.

Recent Observations:
[Memory entries...]
```

This provides rich, multi-dimensional context for the prompt generator to create highly contextual and interesting prompts!

