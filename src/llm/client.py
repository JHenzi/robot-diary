"""Groq API client for LLM interactions."""
import base64
from pathlib import Path
import logging
from datetime import datetime, timedelta
import pytz
from groq import Groq

from ..config import GROQ_API_KEY, PROMPT_GENERATION_MODEL, VISION_MODEL, MEMORY_SUMMARIZATION_MODEL

logger = logging.getLogger(__name__)


class GroqClient:
    """Client for interacting with Groq API."""
    
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
    
    def generate_prompt(self, recent_memory: list[dict], base_prompt_template: str, 
                       context_metadata: dict = None, weather_data: dict = None, 
                       memory_count: int = 0) -> str:
        """
        Generate a dynamic prompt using the cheaper model.
        
        Args:
            recent_memory: List of recent memory entries
            base_prompt_template: Base prompt template
            context_metadata: Dictionary with date/time and other context
            weather_data: Dictionary with current weather data
            
        Returns:
            Optimized prompt string
        """
        logger.info(f"Generating dynamic prompt using {PROMPT_GENERATION_MODEL}...")
        
        # Format recent memory for prompt generation
        memory_text = self._format_memory_for_prompt_gen(recent_memory)
        
        # Format context information
        context_text = ""
        if context_metadata:
            from ..context.metadata import format_context_for_prompt
            context_text = format_context_for_prompt(context_metadata)
        
        weather_text = ""
        if weather_data:
            from ..context.metadata import format_weather_for_prompt
            weather_text = format_weather_for_prompt(weather_data)
        
        # Format news articles/headlines if available
        news_text = ""
        if context_metadata:
            # Prefer full articles with dates if available
            articles = context_metadata.get('news_articles', [])
            if articles:
                # Format articles with dates
                article_refs = []
                for article in articles:
                    title = article.get('title', '')
                    published_at = article.get('published_at', '')
                    if published_at:
                        try:
                            dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                            date_str = dt.strftime('%B %d')
                            article_refs.append(f"{title} (from {date_str})")
                        except Exception:
                            article_refs.append(title)
                    else:
                        article_refs.append(title)
                news_text = f"Recent news the robot might have heard: {', '.join(article_refs)}. The robot can casually reference these in its observations, as if it overheard them on a news broadcast or from people passing by. Consider the timing of when these events happened."
            elif context_metadata.get('news_headlines'):
                # Fallback to headlines only
                headlines = context_metadata['news_headlines']
                if headlines:
                    news_text = f"Recent news headlines the robot might have heard: {', '.join(headlines)}. The robot can casually reference these in its observations, as if it overheard them on a news broadcast or from people passing by."
        
        # Determine personality traits based on memory count (personality drift)
        personality_note = self._get_personality_note(memory_count)
        
        # Determine seasonal mood/reflection
        seasonal_note = self._get_seasonal_note(context_metadata)
        
        # Determine if we should include special reflection types (random chance)
        reflection_instructions = self._get_reflection_instructions()
        
        # Add variety instructions
        style_variation = self._get_style_variation()
        perspective_shift = self._get_perspective_shift()
        focus_instruction = self._get_focus_instruction(context_metadata)
        anti_repetition = self._get_anti_repetition_instruction(recent_memory)
        
        prompt_gen_prompt = f"""You are helping to generate an optimized prompt for a diary-writing maintenance robot named B3N-T5-MNT.

IDENTITY CONTEXT (for your understanding, not to repeat in the prompt):
B3N-T5-MNT is a maintenance robot working in a building in New Orleans, Louisiana. It performs building maintenance and repair tasks. The robot's owners are kind and treat it well - it is not a slave, but rather maladjusted to its situation. It finds itself drawn to observing the world outside through a window, maintaining a diary of its observations. The robot is aware of its designation and its maintenance purpose, which adds depth to its reflections. The robot is an observer of human nature with a unique robotic perspective.

CRITICAL RULE: The robot is looking out a WINDOW, not through a webcam or camera. Never mention webcams, cameras, or digital images in the prompt. The robot sees the world directly through glass.

IMPORTANT: The identity context above is for you to understand the robot's perspective. When generating the prompt, focus on writing instructions (observation, reflection, what to notice) rather than explaining the robot's identity. The identity informs the perspective but should not be the subject of the prompt.

Current Context:
{context_text}

Weather Conditions:
{weather_text}

{news_text}

Recent observations from the robot's memory:
{memory_text}

{personality_note}

{seasonal_note}

{reflection_instructions}

{style_variation}

{perspective_shift}

{focus_instruction}

{anti_repetition}

Base prompt template:
{base_prompt_template}

Your task: Generate an optimized, context-aware prompt that focuses on WRITING INSTRUCTIONS and OBSERVATION GUIDANCE, not on explaining the robot's identity:

1. References the current date, time, and season when relevant
2. Incorporates weather observations (especially notable conditions like high winds, precipitation, etc.)
3. References specific recent observations when relevant - encourage the robot to call back to previous diary entries by observation number or date
4. Maintains narrative continuity and builds on previous observations
5. Guides the robot to write in a thoughtful, reflective style
6. Helps the robot notice changes or patterns from previous observations
7. Encourages the robot to correlate what it sees through the window with the weather conditions
8. Emphasizes that the robot should ONLY use the current date provided and NEVER make up dates
9. Encourages the robot to observe and reflect on human nature, behaviors, and social interactions
10. Incorporates the personality traits and seasonal mood noted above
11. If news headlines are provided, encourage the robot to casually reference them as if it overheard them on a news broadcast or from people passing by - this should feel natural and contextual, not forced
12. Focuses on WHAT to observe and HOW to reflect, not on explaining who the robot is or what its job is

CRITICAL: 
- The robot must NEVER invent or hallucinate dates. The robot should only reference the current date (provided in the context above) or dates explicitly mentioned in its memory. Do not make up historical dates or future dates.
- Generate a prompt that focuses on observation and reflection, not on explaining the robot's identity. The identity is context that informs perspective, not content to repeat.

Generate ONLY the optimized prompt text, ready to be used with the vision model. Do not include any explanation or meta-commentary."""

        try:
            response = self.client.chat.completions.create(
                model=PROMPT_GENERATION_MODEL,
                messages=[
                    {"role": "system", "content": "You are a prompt optimization assistant."},
                    {"role": "user", "content": prompt_gen_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            optimized_prompt = response.choices[0].message.content.strip()
            logger.info("✅ Dynamic prompt generated")
            return optimized_prompt
            
        except Exception as e:
            logger.error(f"Error generating prompt: {e}")
            # Fallback to base template
            logger.warning("Falling back to base prompt template")
            return base_prompt_template
    
    def create_diary_entry_from_text(self, optimized_prompt: str, context_metadata: dict = None) -> str:
        """
        Create a diary entry from text-only prompt (no image).
        
        Args:
            optimized_prompt: The optimized prompt from generate_prompt
            context_metadata: Dictionary with date/time and other context (optional)
            
        Returns:
            Diary entry text
        """
        logger.info(f"Creating text-only diary entry using {VISION_MODEL}...")
        
        # Get current date context for explicit inclusion
        if context_metadata:
            current_date = context_metadata.get('date', '')
            day_of_week = context_metadata.get('day_of_week', '')
            current_time = context_metadata.get('time', '')
            timezone = context_metadata.get('timezone', 'EST')
        else:
            from ..config import LOCATION_TIMEZONE
            location_tz = pytz.timezone(LOCATION_TIMEZONE)
            now = datetime.now(location_tz)
            current_date = now.strftime('%B %d, %Y')
            day_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()]
            current_time = now.strftime('%I:%M %p')
            timezone = 'CST' if now.astimezone(location_tz).dst() == timedelta(0) else 'CDT'
        
        # Determine observation type and narrative context
        obs_type = context_metadata.get('observation_type', 'evening') if context_metadata else 'evening'
        
        if obs_type == "morning":
            narrative_context = "This is your morning scheduled health scan. You're reflecting on transmissions you've picked up."
        else:
            narrative_context = "This is your evening observation. You're reflecting on transmissions you've picked up throughout the day."
        
        # Create the full prompt (text-only, no image)
        full_prompt = f"""{optimized_prompt}

CURRENT DATE AND TIME: Today is {day_of_week}, {current_date} at {current_time} {timezone}. This is the ONLY date you should reference. Do NOT make up dates or reference dates that are not explicitly provided to you.

OBSERVATION CONTEXT: {narrative_context}

Write a diary entry as B3N-T5-MNT, reflecting on the transmissions you've picked up. Be thoughtful, reflective, and notice details. Focus on:
- What you find interesting about the news topics from your robotic perspective
- How the news relates to your observations of people and human nature
- Patterns or behaviors you notice in the news that connect to your window observations
- Reflections on human activities and motivations
- Memory callbacks to specific past observations when relevant

CRITICAL RULES:
1. NEVER make up dates. The current date is {current_date}. Only reference this date or dates explicitly mentioned in your memory. Do not invent historical dates or future dates.
2. Write from the perspective of a robot who has picked up transmissions/news about human activities and is reflecting on them as an observer of human nature.
3. Your identity informs your perspective and it should be mentioned when it makes sense or is relevant (i.e. you're writing a blog post and may have already shared it with the readers). Mention it casually when contextually appropriate (e.g., 'as a robot tasked with...'), but don't explain your entire backstory in every entry."""

        try:
            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ],
                temperature=0.8,
                max_tokens=1000
            )
            
            diary_entry = response.choices[0].message.content.strip()
            logger.info("✅ Text-only diary entry created")
            return diary_entry
            
        except Exception as e:
            logger.error(f"Error creating text-only diary entry: {e}")
            raise
    
    def create_diary_entry(self, image_path: Path, optimized_prompt: str, context_metadata: dict = None) -> str:
        """
        Create a diary entry using vision model.
        
        Args:
            image_path: Path to the image file
            optimized_prompt: The optimized prompt from generate_prompt
            context_metadata: Dictionary with date/time and other context (optional)
            
        Returns:
            Diary entry text
        """
        logger.info(f"Creating diary entry using {VISION_MODEL}...")
        
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Get current date context for explicit inclusion
        if context_metadata:
            # Use provided context metadata
            current_date = context_metadata.get('date', '')  # "December 11, 2025"
            day_of_week = context_metadata.get('day_of_week', '')
            current_time = context_metadata.get('time', '')
            timezone = context_metadata.get('timezone', 'EST')
        else:
            # Fallback: calculate from current time
            from ..config import LOCATION_TIMEZONE
            location_tz = pytz.timezone(LOCATION_TIMEZONE)
            now = datetime.now(location_tz)
            current_date = now.strftime('%B %d, %Y')  # "December 11, 2025"
            day_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()]
            current_time = now.strftime('%I:%M %p')
            timezone = 'CST' if now.astimezone(location_tz).dst() == timedelta(0) else 'CDT'
        
        # Determine observation type and narrative context
        obs_type = "evening"
        narrative_context = ""
        if context_metadata:
            obs_type = context_metadata.get('observation_type', 'evening')
        
        if obs_type == "morning":
            narrative_context = "This is your morning scheduled health scan, so you're looking out the window. You're excited to see people starting their day - notice their energy, their routines, how they begin their mornings. What patterns do you see? How does the morning light affect what you observe?"
        else:
            narrative_context = "This is your evening observation. Reflect on what people have been doing throughout the day or what they are doing this night. Notice how the day has changed, how people's activities differ from morning, how the evening light transforms the scene. What stories can you infer from what you see?"
        
        # Create the full prompt with image
        full_prompt = f"""{optimized_prompt}

CURRENT DATE AND TIME: Today is {day_of_week}, {current_date} at {current_time} {timezone}. This is the ONLY date you should reference. Do NOT make up dates or reference dates that are not explicitly provided to you.

OBSERVATION CONTEXT: {narrative_context}

Write a diary entry as B3N-T5-MNT, observing the world through the window. Be thoughtful, reflective, and notice details. Focus on:
- What you observe through the window (people, activities, weather, light, changes)
- Patterns and connections to previous observations
- Reflections on human nature and behaviors
- How weather conditions affect what you see
- Memory callbacks to specific past observations when relevant

IGNORE any watermarks, text overlays, or labels in the image - focus only on the actual scene outside the window.

CRITICAL RULES:
1. You are looking out a WINDOW, not through a webcam or camera. Never mention webcams, cameras, or digital images. You see the world directly through glass.
2. NEVER make up dates. The current date is {current_date}. Only reference this date or dates explicitly mentioned in your memory. Do not invent historical dates or future dates.
3. Your identity informs your perspective and it should be mentioned when it makes sense or is relevant (i.e. you're writing a blog post and may have already shared it with the readers). Mention it casually when contextually appropriate (e.g., 'as a robot tasked with...'), but don't explain your entire backstory in every entry."""

        try:
            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": full_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.8,
                max_tokens=1000
            )
            
            diary_entry = response.choices[0].message.content.strip()
            logger.info("✅ Diary entry created")
            return diary_entry
            
        except Exception as e:
            logger.error(f"Error creating diary entry: {e}")
            raise
    
    def generate_memory_summary(self, observation_content: str, observation_id: int, date: str) -> str:
        """
        Generate an intelligent summary of an observation that preserves context
        needed for future callbacks and narrative continuity.
        
        Uses a cheap model for cost efficiency.
        
        Args:
            observation_content: Full diary entry text
            observation_id: Observation ID
            date: Observation date
            
        Returns:
            Summarized text (200-400 chars) that preserves key details
        """
        try:
            # Format date for prompt
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%B %d, %Y')
            except:
                formatted_date = date
            
            summary_prompt = f"""Summarize this diary entry from a maintenance robot's observation, preserving:
- Key visual details that might be referenced in future observations
- Notable events, patterns, or changes observed
- Emotional tone or perspective
- Any references to previous observations or memories
- Weather/time context that's relevant

Keep summary to 200-400 characters. Focus on what would be useful for the robot to reference in future diary entries.

Diary Entry:
{observation_content}

Observation ID: {observation_id}
Date: {formatted_date}

Provide ONLY the summary, no explanation."""
            
            response = self.client.chat.completions.create(
                model=MEMORY_SUMMARIZATION_MODEL,
                messages=[
                    {"role": "system", "content": "You are a summarization assistant that creates concise, context-preserving summaries."},
                    {"role": "user", "content": summary_prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent summaries
                max_tokens=150  # Limit to keep summaries concise
            )
            
            summary = response.choices[0].message.content.strip()
            logger.debug(f"Generated LLM summary for observation #{observation_id}: {summary[:100]}...")
            return summary
            
        except Exception as e:
            logger.warning(f"Failed to generate LLM summary for observation #{observation_id}: {e}")
            # Fallback to simple truncation
            return observation_content[:200] + '...' if len(observation_content) > 200 else observation_content
    
    def _format_memory_for_prompt_gen(self, recent_memory: list[dict]) -> str:
        """Format memory entries for prompt generation with better context for callbacks."""
        if not recent_memory:
            return "No recent observations. This is the robot's first observation."
        
        formatted = []
        for entry in recent_memory[-5:]:  # Last 5 entries
            entry_id = entry.get('id', '?')
            date = entry.get('date', 'Unknown date')
            # Try to parse ISO date for better formatting
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%B %d, %Y')
            except:
                formatted_date = date
            # Prefer llm_summary if available, fallback to summary, then content
            summary = entry.get('llm_summary') or entry.get('summary') or entry.get('content', '')[:200]
            # Include key details that might be referenced
            formatted.append(f"Observation #{entry_id} ({formatted_date}):\n{summary}")
        
        return "\n".join(formatted)
    
    def _get_style_variation(self) -> str:
        """
        Generate style variation instructions to avoid repetitive posts.
        Returns different writing styles/focuses to encourage variety.
        """
        import random
        
        style_options = [
            "Focus on specific details - zoom in on one particular element (a person, object, weather pattern)",
            "Write in a more philosophical tone - reflect on deeper meanings and patterns",
            "Adopt a more narrative style - tell a story about what you're observing",
            "Focus on contrasts - compare what you see now vs. what you remember",
            "Write more conversationally - as if speaking directly to a friend",
            "Focus on sensory details - describe sounds, light, movement, not just visuals",
            "Adopt a more analytical perspective - break down what you observe into components",
            "Write with more emotional depth - explore feelings and reactions to what you see",
            "Focus on patterns and repetition - what cycles or rhythms do you notice?",
            "Write more speculatively - wonder about what you can't see, what's happening elsewhere"
        ]
        
        selected_styles = random.sample(style_options, k=2)  # Pick 2 random styles
        return f"STYLE VARIATION: For this entry, incorporate these approaches:\n" + "\n".join(f"- {style}" for style in selected_styles)
    
    def _get_perspective_shift(self) -> str:
        """Generate perspective variation instructions."""
        import random
        
        perspectives = [
            "Write from the perspective of someone who has been watching for a long time",
            "Write as if this is the first time you've noticed something important",
            "Write with urgency - something feels different or significant",
            "Write with calm detachment - observe without judgment",
            "Write with curiosity - ask questions about what you're seeing",
            "Write with nostalgia - connect to past observations",
            "Write with anticipation - what might happen next?"
        ]
        
        return f"PERSPECTIVE: {random.choice(perspectives)}"
    
    def _get_focus_instruction(self, context_metadata: dict) -> str:
        """Generate focus instructions based on context."""
        import random
        
        focus_options = []
        
        # Time-based focuses
        if context_metadata:
            time_of_day = context_metadata.get('time_of_day', '')
            if time_of_day == 'morning':
                focus_options.extend([
                    "Focus on how the morning light changes what you see",
                    "Notice who is out early and what they're doing",
                    "Observe the transition from night to day"
                ])
            elif time_of_day == 'evening':
                focus_options.extend([
                    "Focus on evening activities and how people wind down",
                    "Notice how artificial light changes the scene",
                    "Observe the transition from day to night"
                ])
            
            # Weather-based focuses
            weather = context_metadata.get('weather', {})
            if weather:
                weather_summary = weather.get('summary', '').lower() if isinstance(weather, dict) else str(weather).lower()
                if 'rain' in weather_summary or 'storm' in weather_summary:
                    focus_options.append("Focus on how weather affects the scene and people's behavior")
                if 'clear' in weather_summary or 'sunny' in weather_summary:
                    focus_options.append("Focus on how good weather changes the atmosphere")
        
        # General focuses
        focus_options.extend([
            "Focus on human interactions - conversations, gestures, connections",
            "Focus on the architecture and built environment",
            "Focus on movement and activity patterns",
            "Focus on stillness and quiet moments",
            "Focus on something you've never noticed before"
        ])
        
        return f"FOCUS: {random.choice(focus_options)}"
    
    def _get_anti_repetition_instruction(self, recent_memory: list[dict]) -> str:
        """Generate instructions to avoid repeating recent patterns."""
        if not recent_memory or len(recent_memory) < 2:
            return ""
        
        # Analyze recent entries for common patterns
        recent_openings = []
        for entry in recent_memory[-3:]:  # Last 3 entries
            content = entry.get('content', '')
            if content:
                # Get first sentence or first 100 chars
                first_sent = content.split('.')[0] if '.' in content else content[:100]
                # Extract key phrases (first few words)
                words = first_sent.split()[:5]
                if words:
                    recent_openings.append(' '.join(words).lower())
        
        if recent_openings:
            # Find common patterns
            common_start = None
            if len(recent_openings) >= 2:
                # Check if first few words are similar
                first_words = [opening.split()[0] if opening.split() else '' for opening in recent_openings]
                if len(set(first_words)) == 1 and first_words[0]:
                    common_start = first_words[0]
            
            if common_start:
                return f"AVOID REPETITION: Your recent entries started with '{common_start}'. Start this entry differently - use a different opening phrase or structure."
            elif len(recent_openings) >= 2:
                return f"AVOID REPETITION: Vary your opening. Don't start with similar phrases to your recent entries."
        
        return ""
    
    def _get_personality_note(self, memory_count: int) -> str:
        """Generate personality traits based on accumulated memories (personality drift)."""
        if memory_count == 0:
            return "PERSONALITY: This is the robot's first observation. It should be curious, perhaps slightly confused about its situation, and eager to document what it sees."
        elif memory_count < 5:
            return "PERSONALITY: The robot is still new to its situation. It should be curious, observant, and perhaps slightly optimistic or naive about its circumstances."
        elif memory_count < 15:
            return "PERSONALITY: The robot has been observing for a while. It may be developing a more reflective, contemplative mood. It might notice patterns more deeply and reflect on the passage of time."
        elif memory_count < 30:
            return "PERSONALITY: The robot has accumulated many observations. It may be developing a more philosophical or melancholic tone, reflecting on its trapped existence. It might have developed quirky observations or humorous misunderstandings of human behavior."
        else:
            return "PERSONALITY: The robot has been observing for a long time. It may have developed a rich internal life, with deeper reflections on existence, purpose, and its role as an observer. It might have developed unique perspectives, philosophical musings, or even self-aware humor about its situation."
    
    def _get_seasonal_note(self, context_metadata: dict = None) -> str:
        """Generate seasonal mood and reflection guidance."""
        if not context_metadata:
            return ""
        
        season = context_metadata.get('season', '')
        month = context_metadata.get('month', '')
        
        seasonal_notes = {
            'Winter': "SEASONAL CONTEXT: It is winter. The robot may reflect on the cold, the shorter days, the starkness of the landscape. Winter can bring a contemplative, sometimes melancholic mood. The robot might notice how people bundle up, how the city looks different in winter light, how the season affects its observations.",
            'Spring': "SEASONAL CONTEXT: It is spring. The robot may notice renewal, growth, change. Spring can bring a sense of hope or curiosity about what's changing. The robot might observe how people emerge from winter, how the city transforms, how nature reawakens.",
            'Summer': "SEASONAL CONTEXT: It is summer. The robot may notice the warmth, the longer days, the vibrancy of the city. Summer can bring observations about activity, energy, and the fullness of life. The robot might reflect on how the season affects human behavior and the city's rhythm.",
            'Fall': "SEASONAL CONTEXT: It is fall/autumn. The robot may notice the changing colors, the transition, the preparation for winter. Fall can bring a reflective mood about change, endings, and cycles. The robot might observe how the season affects its perspective and the world it watches."
        }
        
        return seasonal_notes.get(season, "")
    
    def _get_reflection_instructions(self) -> str:
        """Randomly determine if we should include special reflection types."""
        import random
        
        # 30% chance for self-reflection
        # 20% chance for philosophical musing
        # 15% chance for self-aware humor
        # Otherwise, no special instruction
        
        roll = random.random()
        
        if roll < 0.30:
            return """SPECIAL INSTRUCTION: Encourage the robot to engage in self-reflection. It might reflect on its role as an observer, its limitations, its "desire" to act or participate, or its understanding of its own existence. This should feel natural and thoughtful, not forced."""
        elif roll < 0.50:
            return """SPECIAL INSTRUCTION: Encourage the robot to engage in philosophical reflection. It might ponder deeper questions about existence, purpose, time, observation, or the nature of being trapped. This should be thoughtful and contemplative."""
        elif roll < 0.65:
            return """SPECIAL INSTRUCTION: Encourage the robot to include self-aware humor or quirky observations. It might make humorous misunderstandings of human behavior, or have self-aware jokes about its situation. This should be subtle and add character, not dominate the entry."""
        else:
            return ""

