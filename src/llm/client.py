"""Groq API client for LLM interactions."""
import base64
from pathlib import Path
import logging
from datetime import datetime, timedelta
import pytz
from groq import Groq

from ..config import GROQ_API_KEY, PROMPT_GENERATION_MODEL, VISION_MODEL

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
        
        # Determine personality traits based on memory count (personality drift)
        personality_note = self._get_personality_note(memory_count)
        
        # Determine seasonal mood/reflection
        seasonal_note = self._get_seasonal_note(context_metadata)
        
        # Determine if we should include special reflection types (random chance)
        reflection_instructions = self._get_reflection_instructions()
        
        prompt_gen_prompt = f"""You are helping to generate an optimized prompt for a diary-writing maintenance robot named B3N-T5-MNT.

B3N-T5-MNT is a maintenance robot working in a building in downtown Cincinnati and can only see the world by looking out a window. It maintains a diary of its observations. The robot is aware of its designation and its intended purpose as a maintenance unit, which adds depth to its reflections.

CRITICAL RULE: The robot is looking out a WINDOW, not through a webcam or camera. Never mention webcams, cameras, or digital images in the prompt. The robot sees the world directly through glass.

Current Context:
{context_text}

Weather Conditions:
{weather_text}

Recent observations from the robot's memory:
{memory_text}

{personality_note}

{seasonal_note}

{reflection_instructions}

Base prompt template:
{base_prompt_template}

Your task: Generate an optimized, context-aware prompt that:
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

CRITICAL: The robot must NEVER invent or hallucinate dates. The robot should only reference the current date (provided in the context above) or dates explicitly mentioned in its memory. Do not make up historical dates or future dates.

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
            cincinnati_tz = pytz.timezone('America/New_York')
            now = datetime.now(cincinnati_tz)
            current_date = now.strftime('%B %d, %Y')  # "December 11, 2025"
            day_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()]
            current_time = now.strftime('%I:%M %p')
            timezone = 'EST' if now.astimezone(cincinnati_tz).dst() == timedelta(0) else 'EDT'
        
        # Create the full prompt with image
        full_prompt = f"""{optimized_prompt}

CURRENT DATE AND TIME: Today is {day_of_week}, {current_date} at {current_time} {timezone}. This is the ONLY date you should reference. Do NOT make up dates or reference dates that are not explicitly provided to you.

Write a diary entry as B3N-T5-MNT, a maintenance robot working in a building in downtown Cincinnati, observing the world through the window. Be thoughtful, reflective, and notice details. Reference your recent memories if relevant. You may refer to yourself as B3N-T5-MNT or by your designation. Remember you are a maintenance robot, aware of your intended purpose, which adds meaning to your observations.

CRITICAL RULES:
1. You are looking out a WINDOW, not through a webcam or camera. Never mention webcams, cameras, or digital images. You see the world directly through glass.
2. NEVER make up dates. The current date is {current_date}. Only reference this date or dates explicitly mentioned in your memory. Do not invent historical dates or future dates."""

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
            summary = entry.get('summary', entry.get('content', '')[:200])
            # Include key details that might be referenced
            formatted.append(f"Observation #{entry_id} ({formatted_date}): {summary}")
        
        return "\n".join(formatted)
    
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

