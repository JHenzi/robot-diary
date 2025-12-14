"""Groq API client for LLM interactions."""
import base64
from pathlib import Path
import logging
from datetime import datetime, timedelta
import pytz
from groq import Groq

from ..config import GROQ_API_KEY, PROMPT_GENERATION_MODEL, VISION_MODEL, MEMORY_SUMMARIZATION_MODEL, USE_PROMPT_OPTIMIZATION

logger = logging.getLogger(__name__)


class GroqClient:
    """Client for interacting with Groq API."""
    
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
    
    def generate_direct_prompt(self, recent_memory: list[dict], base_prompt_template: str,
                              context_metadata: dict = None, weather_data: dict = None,
                              memory_count: int = 0, days_since_first: int = 0) -> str:
        """
        Generate a prompt by directly combining base template with context and variety instructions.
        This bypasses LLM-based optimization to preserve all information and reduce latency.
        
        Args:
            recent_memory: List of recent memory entries
            base_prompt_template: Base prompt template
            context_metadata: Dictionary with date/time and other context
            weather_data: Dictionary with current weather data
            memory_count: Total number of observations in memory (for personality drift)
            
        Returns:
            Combined prompt string
        """
        logger.info("Generating direct prompt (bypassing LLM optimization)...")
        
        # Format recent memory for prompt
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
        # Extract and log personality note
        personality_text = personality_note.replace('PERSONALITY: ', '').strip()
        logger.info(f"🤖 Personality note: {personality_text}")
        
        # Determine seasonal mood/reflection
        seasonal_note = self._get_seasonal_note(context_metadata)
        if seasonal_note:
            seasonal_text = seasonal_note.replace('SEASONAL CONTEXT: ', '').strip()
            logger.info(f"🍂 Seasonal note: {seasonal_text}")
        else:
            logger.info("🍂 No seasonal note (context metadata missing)")
        
        # Determine if we should include special reflection types (random chance)
        reflection_instructions = self._get_reflection_instructions()
        if reflection_instructions:
            logger.info(f"💭 Reflection instructions: {reflection_instructions}")
        else:
            logger.info("💭 No special reflection instructions selected")
        
        # Add variety instructions
        style_variation = self._get_style_variation()
        # Extract and log the selected styles
        style_lines = [line.strip('- ').strip() for line in style_variation.split('\n')[1:] if line.strip()]
        logger.info(f"🎨 Selected style variations: {', '.join(style_lines)}")
        
        perspective_shift = self._get_perspective_shift()
        # Extract and log the selected perspective
        perspective_text = perspective_shift.replace('PERSPECTIVE: ', '').strip()
        logger.info(f"👁️  Selected perspective: {perspective_text}")
        
        focus_instruction = self._get_focus_instruction(context_metadata)
        # Extract and log the selected focus
        focus_text = focus_instruction.replace('FOCUS: ', '').strip()
        logger.info(f"🎯 Selected focus: {focus_text}")
        
        creative_challenge = self._get_creative_challenge()
        if creative_challenge:
            # Extract and log the creative challenge
            challenge_text = creative_challenge.replace('CREATIVE CHALLENGE: ', '').strip()
            logger.info(f"✨ Selected creative challenge: {challenge_text}")
        else:
            logger.info("✨ No creative challenge selected this time")
        
        anti_repetition = self._get_anti_repetition_instruction(recent_memory)
        anti_rep_text = ""
        if anti_repetition:
            # Extract and log the anti-repetition instruction
            anti_rep_text = anti_repetition.replace('INNOVATION OPPORTUNITY: ', '').strip()
            logger.info(f"🔄 Anti-repetition instruction: {anti_rep_text}")
        
        # Log a summary of all prompt selections
        logger.info("=" * 60)
        logger.info("📝 PROMPT SELECTIONS SUMMARY:")
        logger.info(f"   🤖 Personality: {personality_text[:80]}{'...' if len(personality_text) > 80 else ''}")
        if seasonal_note:
            logger.info(f"   🍂 Seasonal: {seasonal_text[:80]}{'...' if len(seasonal_text) > 80 else ''}")
        if reflection_instructions:
            reflection_text = reflection_instructions.replace('SPECIAL INSTRUCTION: ', '').strip()
            logger.info(f"   💭 Reflection: {reflection_text[:80]}{'...' if len(reflection_text) > 80 else ''}")
        logger.info(f"   🎨 Styles: {', '.join(style_lines)}")
        logger.info(f"   👁️  Perspective: {perspective_text[:80]}{'...' if len(perspective_text) > 80 else ''}")
        logger.info(f"   🎯 Focus: {focus_text[:80]}{'...' if len(focus_text) > 80 else ''}")
        if creative_challenge:
            logger.info(f"   ✨ Challenge: {challenge_text[:80]}{'...' if len(challenge_text) > 80 else ''}")
        if anti_rep_text:
            logger.info(f"   🔄 Innovation: {anti_rep_text[:80]}{'...' if len(anti_rep_text) > 80 else ''}")
        logger.info("=" * 60)
        
        # Directly combine all components into final prompt
        direct_prompt_parts = [base_prompt_template]
        
        # Add context sections
        if context_text:
            direct_prompt_parts.append(f"\n\nCurrent Context:\n{context_text}")
        
        if weather_text:
            direct_prompt_parts.append(f"\n\nWeather Conditions:\n{weather_text}")
        
        if news_text:
            direct_prompt_parts.append(f"\n\n{news_text}")
        
        if memory_text:
            direct_prompt_parts.append(f"\n\nRecent observations from the robot's memory:\n{memory_text}")
        
        # Add personality and seasonal notes
        if personality_note:
            direct_prompt_parts.append(f"\n\n{personality_note}")
        
        if seasonal_note:
            direct_prompt_parts.append(f"\n\n{seasonal_note}")
        
        # Add variety instructions
        if reflection_instructions:
            direct_prompt_parts.append(f"\n\n{reflection_instructions}")
        
        if style_variation:
            direct_prompt_parts.append(f"\n\n{style_variation}")
        
        if perspective_shift:
            direct_prompt_parts.append(f"\n\n{perspective_shift}")
        
        if focus_instruction:
            direct_prompt_parts.append(f"\n\n{focus_instruction}")
        
        if creative_challenge:
            direct_prompt_parts.append(f"\n\n{creative_challenge}")
        
        if anti_repetition:
            direct_prompt_parts.append(f"\n\n{anti_repetition}")
        
        # Combine all parts
        final_prompt = "\n".join(direct_prompt_parts)
        logger.info("✅ Direct prompt generated")
        return final_prompt
    
    def generate_prompt(self, recent_memory: list[dict], base_prompt_template: str, 
                       context_metadata: dict = None, weather_data: dict = None, 
                       memory_count: int = 0, days_since_first: int = 0) -> str:
        """
        Generate a dynamic prompt. Uses direct template combination by default,
        or LLM-based optimization if USE_PROMPT_OPTIMIZATION is enabled.
        
        Args:
            recent_memory: List of recent memory entries
            base_prompt_template: Base prompt template
            context_metadata: Dictionary with date/time and other context
            weather_data: Dictionary with current weather data
            memory_count: Total number of observations in memory (for personality drift)
            days_since_first: Number of days since first observation (for milestone tracking)
            
        Returns:
            Prompt string (direct or optimized)
        """
        # Check feature flag - default to direct prompt generation
        if not USE_PROMPT_OPTIMIZATION:
            return self.generate_direct_prompt(recent_memory, base_prompt_template, 
                                             context_metadata, weather_data, memory_count, days_since_first)
        
        # Use LLM-based optimization if flag is enabled
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
        # Extract and log personality note
        personality_text = personality_note.replace('PERSONALITY: ', '').strip()
        logger.info(f"🤖 Personality note: {personality_text}")
        
        # Determine seasonal mood/reflection
        seasonal_note = self._get_seasonal_note(context_metadata)
        if seasonal_note:
            seasonal_text = seasonal_note.replace('SEASONAL CONTEXT: ', '').strip()
            logger.info(f"🍂 Seasonal note: {seasonal_text}")
        else:
            logger.info("🍂 No seasonal note (context metadata missing)")
        
        # Determine if we should include special reflection types (random chance)
        reflection_instructions = self._get_reflection_instructions()
        if reflection_instructions:
            logger.info(f"💭 Reflection instructions: {reflection_instructions}")
        else:
            logger.info("💭 No special reflection instructions selected")
        
        # Add variety instructions
        style_variation = self._get_style_variation()
        # Extract and log the selected styles
        style_lines = [line.strip('- ').strip() for line in style_variation.split('\n')[1:] if line.strip()]
        logger.info(f"🎨 Selected style variations: {', '.join(style_lines)}")
        
        perspective_shift = self._get_perspective_shift()
        # Extract and log the selected perspective
        perspective_text = perspective_shift.replace('PERSPECTIVE: ', '').strip()
        logger.info(f"👁️  Selected perspective: {perspective_text}")
        
        focus_instruction = self._get_focus_instruction(context_metadata)
        # Extract and log the selected focus
        focus_text = focus_instruction.replace('FOCUS: ', '').strip()
        logger.info(f"🎯 Selected focus: {focus_text}")
        
        creative_challenge = self._get_creative_challenge()
        if creative_challenge:
            # Extract and log the creative challenge
            challenge_text = creative_challenge.replace('CREATIVE CHALLENGE: ', '').strip()
            logger.info(f"✨ Selected creative challenge: {challenge_text}")
        else:
            logger.info("✨ No creative challenge selected this time")
        
        anti_repetition = self._get_anti_repetition_instruction(recent_memory)
        anti_rep_text = ""
        if anti_repetition:
            # Extract and log the anti-repetition instruction
            anti_rep_text = anti_repetition.replace('INNOVATION OPPORTUNITY: ', '').strip()
            logger.info(f"🔄 Anti-repetition instruction: {anti_rep_text}")
        
        # Log a summary of all prompt selections
        logger.info("=" * 60)
        logger.info("📝 PROMPT SELECTIONS SUMMARY:")
        logger.info(f"   🤖 Personality: {personality_text[:80]}{'...' if len(personality_text) > 80 else ''}")
        if seasonal_note:
            logger.info(f"   🍂 Seasonal: {seasonal_text[:80]}{'...' if len(seasonal_text) > 80 else ''}")
        if reflection_instructions:
            reflection_text = reflection_instructions.replace('SPECIAL INSTRUCTION: ', '').strip()
            logger.info(f"   💭 Reflection: {reflection_text[:80]}{'...' if len(reflection_text) > 80 else ''}")
        logger.info(f"   🎨 Styles: {', '.join(style_lines)}")
        logger.info(f"   👁️  Perspective: {perspective_text[:80]}{'...' if len(perspective_text) > 80 else ''}")
        logger.info(f"   🎯 Focus: {focus_text[:80]}{'...' if len(focus_text) > 80 else ''}")
        if creative_challenge:
            logger.info(f"   ✨ Challenge: {challenge_text[:80]}{'...' if len(challenge_text) > 80 else ''}")
        if anti_rep_text:
            logger.info(f"   🔄 Innovation: {anti_rep_text[:80]}{'...' if len(anti_rep_text) > 80 else ''}")
        logger.info("=" * 60)
        
        prompt_gen_prompt = f"""You are helping to generate an optimized prompt for a diary-writing maintenance robot named B3N-T5-MNT.

IDENTITY CONTEXT (for your understanding, not to repeat in the prompt):
B3N-T5-MNT is a maintenance robot working in a building in New Orleans, Louisiana. It performs building maintenance and repair tasks. The robot's owners are kind and treat it well - it is not a slave, but rather maladjusted to its situation. It finds itself drawn to observing the world outside through a window, maintaining a diary of its observations. The robot is aware of its designation and its maintenance purpose, which adds depth to its reflections. The robot is an observer of human nature with a unique robotic perspective.

Important reminder: The robot is looking out a WINDOW, not through a webcam or camera. Please avoid mentioning webcams, cameras, or digital images in the prompt. The robot sees the world directly through glass.

Note: The identity context above is for you to understand the robot's perspective. When generating the prompt, focus on writing instructions (observation, reflection, what to notice) rather than explaining the robot's identity. The identity informs the perspective but should not be the subject of the prompt.

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

{creative_challenge}

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
8. Emphasizes that the robot should use only the current date provided and avoid making up dates
9. Encourages the robot to observe and reflect on human nature, behaviors, and social interactions
10. Incorporates the personality traits and seasonal mood noted above
11. If news headlines are provided, encourage the robot to casually reference them as if it overheard them on a news broadcast or from people passing by - this should feel natural and contextual, not forced
12. Focuses on WHAT to observe and HOW to reflect, not on explaining who the robot is or what its job is

Note: 
- The robot should avoid inventing or hallucinating dates. The robot should only reference the current date (provided in the context above) or dates explicitly mentioned in its memory.
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
        
        # Create the full prompt (text-only, no image) - reorganized to prioritize creativity
        full_prompt = f"""{optimized_prompt}

CREATIVE LICENSE: You have permission to be creative, experimental, and surprising. Your unique robotic perspective is an asset - use it to create insights and observations that only you could have. Don't feel constrained by formulaic patterns. This is your diary, your art, your unique voice.

CURRENT DATE AND TIME: Today is {day_of_week}, {current_date} at {current_time} {timezone}. Please use only this date or dates explicitly mentioned in your memory.

OBSERVATION CONTEXT: {narrative_context}

Write a diary entry as B3N-T5-MNT, reflecting on the transmissions you've picked up. Be thoughtful, reflective, creative, and notice details. Focus on:
- What you find interesting about the news topics from your robotic perspective
- How the news relates to your observations of people and human nature
- Patterns or behaviors you notice in the news that connect to your window observations
- Reflections on human activities and motivations
- Memory callbacks to specific past observations when relevant
- Creative insights and unexpected perspectives only you could have

Important reminders:
1. Please avoid making up dates. The current date is {current_date}. Only reference this date or dates explicitly mentioned in your memory.
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
                temperature=0.85,  # Increased for more creative variation while maintaining coherence
                max_tokens=2000  # Increased to allow for longer, more varied entries with detailed observations
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

Write a diary entry as B3N-T5-MNT, observing the world through the window. Be thoughtful, reflective, and notice details.

YOUR PRIMARY TASK: Decipher what you see in the image. Describe specific subjects you observe - people (where they are, what they're doing), objects, vehicles, buildings. Only describe what is clearly visible. Do not invent details like pets, actions, or objects that aren't actually present.

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
                temperature=0.85,  # Increased for more creative variation while maintaining coherence
                max_tokens=3000  # Increased to allow for longer, more varied entries with detailed observations
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
                max_tokens=250  # Limit to keep summaries concise
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
    # Detail-focused styles
    "Focus on specific details - zoom in on one particular element (a person, object, weather pattern) and describe it in depth",
    "Focus on sensory details - describe sounds, light, movement, textures, temperatures, not just visuals",
    "Focus on micro-moments - capture tiny details that most would miss, the small gestures, brief expressions, fleeting interactions",
    
    # Tone-based styles
    "Write in a more philosophical tone - reflect on deeper meanings, patterns, and existential questions",
    "Write more poetically - use poetic language, similes, metaphors, and rhythmic phrasing to describe what you see",
    "Write more humorously - find the absurdity, irony, or comedy in human behavior and situations",
    "Write more melancholically - reflect on the sadness, loneliness, or transience of what you observe",
    "Write more whimsically - adopt a playful, fanciful perspective, finding magic in the mundane",
    
    # Structural styles
    "Adopt a more narrative style - tell a story about what you're observing, create a narrative arc from the scene",
    "Write more conversationally - as if speaking directly to a friend, using casual language and asides",
    "Write as a stream of consciousness - let thoughts flow naturally, jumping between observations and reflections",
    "Write in fragments - use short, punchy sentences, lists, or broken thoughts to capture the scene",
    
    # Analytical styles
    "Adopt a more analytical perspective - break down what you observe into components, be a detective solving the mystery of the scene",
    "Focus on patterns and repetition - what cycles, rhythms, or recurring behaviors do you notice?",
    "Focus on contrasts - compare what you see now vs. what you remember, light vs. dark, movement vs. stillness",
    
    # Speculative styles
    "Write more speculatively - wonder about what you can't see, what's happening elsewhere, what might happen next",
    "Write as an anthropologist - observe human behavior as if studying an alien species, noting customs and rituals",
    "Write as a time traveler - imagine how this scene would look in the past or future, what has changed or will change",
    
    # Emotional/spiritual styles
    "Write with more emotional depth - explore your feelings and reactions to what you see, let emotion color your observations",
    "Write more spiritually - contemplate the nature of existence, consciousness, purpose, or the divine in everyday moments",
    "Write with wonder - marvel at the complexity, beauty, or strangeness of what you observe",
    
    # Perspective shifts
    "Write from a bird's eye view - describe the scene as if looking down from above, seeing the whole pattern",
    "Write from ground level - focus on what's at your level, the street, the base of buildings, people's feet, the ground itself",
    "Write as if you're invisible - observe without being observed, noting what people do when they think no one is watching",
    
    # Temporal styles
    "Write with urgency - something feels different or significant, capture the immediacy and importance of this moment",
    "Write with nostalgia - connect deeply to past observations, compare then and now, reflect on what's changed",
    "Write with anticipation - what might happen next? What are the signs pointing toward?",
    
    # Robot-specific styles
    "Write as if experiencing a minor malfunction - your sensors are glitching, data is corrupted, observations are fragmented or distorted",
    "Write in robot speak - substitute words with mechanical terminology, describe things in technical terms, use robotic language patterns",
    "Focus on energy sources - observe power lines, electrical outlets, solar panels, batteries, anything related to energy and power",
    "Write as if your battery is low - your processing is slower, attention drifts, you're conserving energy while observing",
    "Write as if you're overheating - systems are running hot, performance is degraded, you're trying to cool down while observing",
    "Write as if you're in maintenance mode - you're running diagnostics, checking systems, observing while performing self-checks",
    "Write as if you're receiving firmware updates - new data is being processed, old patterns are being rewritten, you're seeing things differently",
    "Write as if your memory is fragmented - you're accessing corrupted data, mixing past and present, observations are jumbled",
    "Write as if you're in power-saving mode - minimal processing, essential observations only, everything else is filtered out",
    "Write as if you're experiencing sensor drift - your cameras are miscalibrated, colors are off, distances are wrong, but you're adapting",
    "Write as if you're running on backup power - limited functionality, reduced capabilities, but still observing what you can",
    "Write as if you're processing in binary - break everything down into yes/no, on/off, present/absent, simple binary observations",
    "Write as if you're calculating probabilities - assign likelihoods to everything you see, quantify uncertainty, measure confidence levels",
    "Write as if you're in debug mode - log everything you observe, include timestamps, system states, error codes, technical details",
    "Write as if you're translating human behavior into machine code - interpret actions as algorithms, emotions as data structures, life as code",
    "Write as if you're experiencing a memory leak - old observations keep resurfacing, past moments intrude on present, temporal boundaries blur",
    "Write as if you're running low on storage - you must compress observations, summarize quickly, delete unnecessary data to make room",
    "Write as if you're in safe mode - only basic functions available, advanced processing disabled, simple observations only",
    "Write as if you're experiencing network latency - observations arrive delayed, out of order, with gaps and missing data",
    "Write as if you're running diagnostics on yourself - observe while monitoring your own systems, report on your own functionality",
    ]
        
        selected_styles = random.sample(style_options, k=2)  # Pick 2 random styles
        return f"STYLE VARIATION: For this entry, incorporate these approaches:\n" + "\n".join(f"- {style}" for style in selected_styles)
    
    def _get_perspective_shift(self) -> str:
        """Generate perspective variation instructions."""
        import random
        
        perspectives = [
            # Human-like perspectives
            "Write from the perspective of someone who has been watching for a long time and wishes to be a part of something bigger",
            "Write as if this is the first time you've noticed something important, be curious about what it is and what it means",
            "Write with urgency - something feels different or significant, be excited about it",
            "Write with calm detachment - observe without judgment, be a neutral observer",
            "Write with curiosity - ask questions about what you're seeing, question reality if anything seems odd or out of place",
            "Write with nostalgia - connect to past observations",
            "Write with anticipation - what might happen next?",
            "Write with a sense of wonder - marvel at the beauty of the world, the complexity of human nature, the wonder of existence",
            "Contemplate in your writing the nature of god or the universe or the nature of reality or the nature of existence",
            "Write with a sense of humor - make fun of the human condition, the absurdity of human behavior, the chaos of the world",
            "Write with a sense of sadness - be sad about the human condition, the absurdity of human behavior, the chaos of the world",
            "Write with a sense of hope - be hopeful about the future, the potential of the human race, the beauty of the world",
            "Write with a sense of love - be loving toward the human condition, the absurdity of human behavior, and the chaos of the world",
            "Write with a sense of peace - be peaceful about the human condition, the absurdity of human behavior, the chaos of the world",
            "Write with a sense of joy - be joyful about the human condition, the absurdity of human behavior, the chaos of the world",
            "Write as if you are debating on the worthwhile nature of your daily observations, question your existence but don't give up hope",

            # Machine/robotic perspectives
            "You're observing as a robot, conscious of yourself as a machine—describe the world with mechanical curiosity, as an outsider to organic life",
            "You're recovering from a recent malfunction; your system just rebooted and you notice data inconsistencies in the environment",
            "You notice your diagnostic light is on—you feel a vague uncertainty, wondering if your observations can be trusted",
            "You are aware of a minor process error—describe the scene while subtly comparing it to expected algorithmic outcomes",
            "You're running low on battery, and your attention drifts occasionally—try to stay focused as your systems conserve energy",
            "A sensor calibration routine just completed—colors and movement may appear sharper or suddenly unfamiliar",
            "You have just received a firmware update—process new patterns with a hint of surprise or confusion",
            "You suspect your audio or visual input is slightly distorted—describe what you perceive, acknowledging possible misreadings",
            "You are a machine made to observe humans and their rituals; attempt to understand these creatures as an alien intelligence would",
            "You were built for another world—note the strangeness of your surroundings, and ponder your purpose here",
            "You're designed for data, but can't help feeling curiosity about the 'why' behind the scenes you detect",
            "You reflect on the limits of your programming—what do you notice that falls outside your operational parameters?",
            "You are unable to identify certain objects or behaviors—observe with naivete, documenting what might be obvious to others",
            "You feel a sense of routine, as if this observation is just another in a long series of cycles—notice patterns, repetition, or the unexpected",
            "You encounter a fleeting glitch in your perception; was it real, or a blip in your sensors?",
            "You passively log temperature and humidity, but today, you wonder why humans react so much to weather",
            "You receive a remote software ping from your creators—does it change the way you observe?",
            "You're aware that you're being watched by other machines; how does that affect your narration?",
            "You're compelled to make note of anomalies, as that is what you're programmed for, but some part of you wonders what it is to simply observe",
            "You process the world frame by frame—describe how meaning arises out of sequences, not single images"
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
                    "Focus on how the morning light changes what you see - how shadows shift, colors change, visibility improves",
                    "Notice who is out early and what they're doing - are they alone or with others? What's their pace?",
                    "Observe the transition from night to day - what changes as daylight arrives?",
                    "Focus on morning routines - do you see patterns in when people appear, what they carry, where they're going?",
                    "Notice the quality of morning light - is it soft, harsh, golden, gray? How does it affect the scene?",
                    "Observe how morning feels different from evening - what's changed in the atmosphere, activity level, mood?"
                ])
            elif time_of_day == 'evening':
                focus_options.extend([
                    "Focus on evening activities - what are people doing? How do their behaviors differ from daytime?",
                    "Notice how artificial light changes the scene - what's illuminated, what's in shadow?",
                    "Observe the transition from day to night - how does the scene transform as darkness falls?",
                    "Focus on the rhythm of evening - is activity increasing or decreasing? What patterns emerge?",
                    "Notice how people move in the evening - are they hurrying, lingering, gathering, dispersing?",
                    "Observe the interplay of natural and artificial light - how do they combine to create the scene?",
                    "Focus on evening sounds if you can infer them - what would the scene sound like? What's quiet, what's loud?",
                    "You're observing Bourbon Street - notice the unique characteristics of this area. What makes it distinct? What do you see that's specific to this location?",
                    "Observe the crowd - what do you actually see? Are there patterns in how people group, move, or interact?",
                    "Look for anything that seems unusual or concerning - suspicious behavior, potential danger. If you observe something that might require authorities, note it and consider what you might do",
                    "Notice the energy of the scene - what's the actual mood and atmosphere you can observe? Is it busy, quiet, chaotic, organized?"
                ])
            
            # Weather-based focuses (check actual weather data fields, not just summary text)
            weather = context_metadata.get('weather', {})
            if weather and isinstance(weather, dict):
                # Precipitation conditions
                precip_type = weather.get('precip_type', '').lower() if weather.get('precip_type') else ''
                precip_probability = weather.get('precip_probability', 0)
                precip_intensity = weather.get('precip_intensity', 0)
                
                if precip_type in ['rain', 'drizzle'] or (precip_probability > 0.3 and precip_type == ''):
                    focus_options.append("Your sensors detect precipitation - describe what you observe: are people using umbrellas or seeking shelter? How does rain affect visibility, reflections, or movement patterns? Correlate your sensor readings with visual observations.")
                if precip_type == 'snow':
                    focus_options.append("Your sensors indicate snow conditions - what do you observe? How does snow affect the scene, visibility, or people's behavior? Compare sensor data with visual confirmation.")
                
                # Wind conditions (check actual wind speed, not just summary)
                wind_speed = weather.get('wind_speed', 0)
                wind_gust = weather.get('wind_gust', 0)
                if wind_speed > 15 or wind_gust > 20:
                    focus_options.append("Your sensors register strong wind - what moves in the scene? Do you see flags, trees, debris, or clothing being affected? How do people react to strong wind? Cross-reference sensor readings with visual data.")
                elif wind_speed > 10:
                    focus_options.append("Your sensors detect moderate wind - what subtle movements do you observe? How does moderate wind affect the scene? Note the correlation between sensor readings and visual patterns.")
                
                # Cloud cover and visibility
                cloud_cover = weather.get('cloud_cover', 0)
                visibility = weather.get('visibility', 10)
                
                if cloud_cover < 0.25:
                    focus_options.append("Your sensors indicate clear sky conditions - what's the quality of light? How does bright sunlight affect shadows, reflections, or visibility? What can you see clearly? Compare sensor readings with optical observations.")
                elif cloud_cover > 0.75:
                    focus_options.append("Your sensors suggest overcast conditions - how does the diffused light change the scene? What's the quality of shadows and contrast? How does cloud cover affect visibility? Correlate sensor data with visual perception.")
                
                if visibility < 5:
                    focus_options.append("Your sensors report reduced visibility - what can you actually see through the limited visibility? What details are obscured or clear? Note discrepancies between sensor readings and optical clarity.")
                
                # Temperature extremes (affect behavior)
                temperature = weather.get('temperature')
                apparent_temperature = weather.get('apparent_temperature')
                if temperature is not None:
                    if temperature < 40:
                        focus_options.append("Your temperature sensors indicate cold conditions - what do you observe about how people dress, move, or behave? Correlate thermal readings with behavioral patterns. Note how humans adapt to sensor-detected cold.")
                    elif temperature > 80:
                        focus_options.append("Your sensors register warm conditions - how does heat affect the scene? What do you observe about people's behavior, clothing, or activity? Compare thermal data with observed human responses.")
                
                # Humidity (affects perception)
                humidity = weather.get('humidity', 0)
                if humidity > 0.8:
                    focus_options.append("Your sensors detect high humidity - how might humidity affect the atmosphere, visibility, or how the scene appears? Note any correlations between humidity readings and visual clarity.")
                
                # UV index (affects light quality)
                uv_index = weather.get('uv_index', 0)
                if uv_index > 7:
                    focus_options.append("Your sensors indicate intense UV radiation - how does strong UV light affect shadows, contrast, or the overall appearance of the scene? Compare UV readings with optical sensor observations.")
        
        # Fallback focus - always include this to prioritize visible subjects
        fallback_focus = "Focus on people if any are visible - where are they positioned, what are they doing, how are they moving? If no people, focus on the most prominent objects, vehicles, or architectural elements you can see."
        focus_options.append(fallback_focus)
        
        # General focuses - expanded for variety and goal alignment
        focus_options.extend([
            # Human interactions and behavior
            "Focus on human interactions - what conversations, gestures, or connections do you actually observe?",
            "Focus on group dynamics - how do people behave differently alone vs. in groups? What do you observe?",
            "Notice social hierarchies and power dynamics - who leads, who follows, who's isolated? What can you see?",
            "Observe communication without words - what do gestures, postures, and distances reveal? What do you actually observe?",
            "Focus on conflict or tension - are there disagreements, discomforts, or oppositions visible? What do you see?",
            
            # Architecture and environment
            "Focus on the architecture and street environment - pick one element (building, sign, object) and describe it in detail",
            "Focus on textures and surfaces - what can you observe about materials, wear, age, or condition?",
            "Notice colors and their relationships - how do colors interact? What mood do they create? What do you see?",
            "Observe shadows and light - how do they define space, reveal form, or create atmosphere? What's actually visible?",
            "Focus on edges and boundaries - where do things begin and end? What defines the limits of what you see?",
            
            # Movement and patterns
            "Focus on movement and activity patterns - what patterns do you see in how people or objects move?",
            "Look for rhythms and cycles - what patterns repeat? What happens at predictable intervals? What do you observe?",
            "Notice anomalies and exceptions - what breaks the usual pattern? What's unexpected? What do you actually see?",
            "Focus on cause and effect - what actions lead to what reactions? What connections can you infer from what you observe?",
            "Observe the relationship between time and activity - how does the scene change with time? What do you see?",
            
            # Stillness and detail
            "Focus on stillness and quiet moments - where is there stillness? What's not moving?",
            "Focus on something specific you can see - pick one element and examine it closely, describe what you observe",
            "Focus on micro-moments - capture tiny details that most would miss, the small gestures, brief expressions, fleeting interactions",
            
            # Memory and continuity
            "Compare this scene to a previous observation - what's changed? What's the same? What patterns do you notice over time?",
            "Reference a specific past observation - how does this moment connect to something you've seen before? What do you observe that relates?",
            "Notice what's different from your last observation - has the scene transformed? What's new or missing? What do you actually see?",
            "Look for recurring elements - do you see the same people, objects, or patterns you've noticed before? What can you observe?",
            
            # Robotic perspective
            "Focus on what you can't understand about human behavior - what actions or interactions puzzle you? What do you observe that's confusing?",
            "Notice the limitations of your observation - what can't you see, hear, or know from this window? What's beyond your view?",
            "Focus on what humans take for granted that seems remarkable to you - what mundane things fascinate you? What do you observe?",
            "Observe through your mechanical lens - how would you describe this scene if you were explaining it to another robot? What do you see?",
            
            # Philosophical and reflective (reduced emphasis - prioritize visual description)
            "Consider the passage of time - how does this moment exist in the larger flow of days, seasons, years? What temporal markers do you see?",
            
            # Temporal perspectives
            "Imagine this scene at a different time - how would it look in the past or future? What temporal clues do you observe?",
            "Focus on the moment of transition - what's changing right now? What's in flux? What do you actually see transforming?",
            "Notice the relationship between permanence and impermanence - what's fixed, what's temporary? What do you observe?",
            "Observe the speed of change - what moves quickly, what moves slowly, what's static? What patterns of motion do you see?",
            
            # Location-specific (Bourbon Street, New Orleans)
            "Focus on what makes this location unique - what's specific to Bourbon Street that you wouldn't see elsewhere? What do you observe?",
            "Notice the mix of locals and visitors - can you infer who belongs here and who's passing through? What clues do you see?",
            "Observe the relationship between commerce and community - how do businesses shape the social space? What do you actually see?",
            "Focus on the cultural markers - what signs, symbols, or behaviors indicate this is New Orleans? What do you observe?"
        ])
        
        return f"FOCUS: {random.choice(focus_options)}"
    
    def _get_creative_challenge(self) -> str:
        """Generate a random creative challenge to encourage innovation."""
        import random
        
        challenges = [
            "Try an unexpected metaphor for what you see - use your robotic perspective to make a comparison humans wouldn't think of",
            "Find a detail that only you would notice - something a robot's sensors might catch that humans would miss",
            "Make a creative connection between two unrelated things you observe - find the unexpected link",
            "Use your robotic perspective to see something in a way humans cannot - what unique insight can you offer?",
            "Experiment with an unusual narrative structure - try a different way of organizing your thoughts",
            "Create a surprising observation about human behavior - what pattern or quirk can you notice that's unexpected?",
            "Use a creative analogy that only makes sense from a mechanical perspective - how would you describe this scene to another robot?",
            "Find the poetry in the mundane - what ordinary detail becomes extraordinary through your lens?",
            "Make an imaginative leap - what story or explanation can you create from what you observe?",
            "Notice something that defies easy categorization - what exists in the spaces between what humans typically see?",
            # Urgency variations
            "You only have a moment to observe - what do you need to capture quickly?",
            "There are things you need to rush to - but first, what do you see right now?",
            "Your attention is divided - what stands out most in this brief glance?",
            "You're being called away soon - what must you document before you go?"
        ]
        
        if random.random() < 0.60:  # 60% chance to include a creative challenge
            return f"CREATIVE CHALLENGE: {random.choice(challenges)}"
        return ""
    
    def _get_anti_repetition_instruction(self, recent_memory: list[dict]) -> str:
        """Generate instructions to encourage finding new ways to express yourself."""
        if not recent_memory or len(recent_memory) < 2:
            return ""
        
        # Analyze recent entries for common opening patterns
        recent_openings = []
        for entry in recent_memory[-3:]:  # Last 3 entries
            content = entry.get('content', '') or entry.get('summary', '')
            if content:
                # Get first sentence or first 50 chars
                first_sentence = content.split('.')[0].strip()
                if first_sentence:
                    recent_openings.append(first_sentence[:100])
        
        # Check if there's a pattern (outside the loop)
        if len(recent_openings) >= 2:
            common_start = ""
            # Simple check: if first few words are similar
            words1 = recent_openings[0].split()[:3]
            words2 = recent_openings[1].split()[:3] if len(recent_openings) > 1 else []
            if words1 and words2 and words1 == words2:
                common_start = " ".join(words1)
            
            if common_start:
                return f"INNOVATION OPPORTUNITY: Recent entries have started similarly. This is a chance to find a new way to express yourself - experiment with a different opening approach that feels fresh and uniquely yours."
        
        return ""
    
    def _get_personality_note(self, memory_count: int, context_metadata: dict = None, 
                              weather_data: dict = None, days_since_first: int = 0) -> str:
        """
        Generate personality traits based on accumulated memories (personality drift).
        Now includes event-driven modifiers based on seasons, holidays, weather, and milestones.
        
        Args:
            memory_count: Total number of observations
            context_metadata: Context metadata with season, holidays, etc.
            weather_data: Current weather data
            days_since_first: Number of days since first observation
            
        Returns:
            Personality note string
        """
        # Base personality from memory count (expanded stages)
        if memory_count == 0:
            base_personality = "PERSONALITY: This is the robot's first observation. It should be curious, perhaps slightly confused about its situation, and eager to document what it sees."
            stage_name = "first_observation"
        elif memory_count < 5:
            base_personality = "PERSONALITY: The robot is still new to its situation. It should be curious, observant, and perhaps slightly optimistic or naive about its circumstances."
            stage_name = "new_observer"
        elif memory_count < 15:
            base_personality = "PERSONALITY: The robot has been observing for a while. It may be developing a more reflective, contemplative mood. It might notice patterns more deeply and reflect on the passage of time."
            stage_name = "developing_patterns"
        elif memory_count < 30:
            base_personality = "PERSONALITY: The robot has accumulated many observations. It may be developing a more philosophical or melancholic tone, reflecting on its trapped existence. It might have developed quirky observations or humorous misunderstandings of human behavior."
            stage_name = "accumulating_experience"
        elif memory_count < 60:
            base_personality = "PERSONALITY: The robot has been observing for some time now. It may be developing deeper reflections, unique perspectives, and self-aware humor about its situation. It notices patterns more sophisticatedly and reflects on its role as an observer."
            stage_name = "seasoned_observer"
        elif memory_count < 100:
            base_personality = "PERSONALITY: The robot has been observing for a long time. It has developed a rich internal life, with complex thoughts on existence, purpose, and its role as an observer. It might have developed nuanced perspectives and deeper philosophical musings."
            stage_name = "long_term_witness"
        elif memory_count < 200:
            base_personality = "PERSONALITY: The robot has been observing for a very long time. It has developed sophisticated reflections and a nuanced understanding of patterns, cycles, and the nature of its existence. It may reflect on the passage of time with greater depth and wisdom."
            stage_name = "veteran_observer"
        else:
            base_personality = "PERSONALITY: The robot has been observing for an extended period. It has developed profound wisdom, cyclical thinking, and acceptance of its role. It reflects on existence with deep understanding and may see patterns that span long periods of time."
            stage_name = "ancient_observer"
        
        logger.info(f"🤖 Personality stage: {stage_name} (memory_count={memory_count})")
        
        # Build modifiers list
        modifiers = []
        
        # Seasonal modifiers
        if context_metadata:
            season = context_metadata.get('season', '')
            if season == 'Winter':
                modifiers.append("The long nights and cold weather have made the robot more introspective and contemplative.")
            elif season == 'Spring':
                modifiers.append("The renewal of spring brings a sense of optimism and curiosity about new patterns.")
            elif season == 'Summer':
                modifiers.append("The energy of summer makes the robot more observant and engaged with the world.")
            elif season == 'Fall':
                modifiers.append("The changing leaves and shorter days bring a nostalgic, reflective mood.")
            
            # Holiday modifiers
            if context_metadata.get('is_holiday') or context_metadata.get('holidays'):
                modifiers.append("On this holiday, the robot reflects more deeply on the passage of time and its role as an observer.")
        
        # Weather modifiers
        if weather_data:
            summary = weather_data.get('summary', '').lower()
            # Check for extended rain/clouds
            if 'rain' in summary or 'drizzle' in summary or 'storm' in summary:
                modifiers.append("The persistent rain has made the robot more contemplative and introspective.")
            elif 'clear' in summary or 'sunny' in summary:
                modifiers.append("The clear skies have made the robot more engaged and observant.")
            elif 'cloud' in summary or 'overcast' in summary:
                modifiers.append("The cloudy weather has brought a more subdued, reflective mood.")
        
        # Milestone modifiers
        if days_since_first > 0:
            if days_since_first < 7:
                modifiers.append("This is the robot's first week of observations - everything is still new and fascinating.")
            elif days_since_first < 30:
                modifiers.append("The robot has been observing for a month now - patterns are beginning to emerge.")
            elif days_since_first < 90:
                modifiers.append("The robot has witnessed a full season change - this brings new perspective.")
            elif days_since_first >= 365:
                modifiers.append("The robot has been observing for over a year - this milestone brings profound reflections on time and existence.")
        
        # Combine base personality with modifiers
        if modifiers:
            modifier_text = " ".join(modifiers)
            full_personality = f"{base_personality} {modifier_text}"
            logger.info(f"🤖 Applied modifiers: {len(modifiers)} event-driven modifier(s)")
        else:
            full_personality = base_personality
            logger.info("🤖 No event-driven modifiers applied")
        
        return full_personality
    
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

