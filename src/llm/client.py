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
                       context_metadata: dict = None, weather_data: dict = None) -> str:
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
        
        prompt_gen_prompt = f"""You are helping to generate an optimized prompt for a diary-writing maintenance robot named B3N-T5-MNT.

B3N-T5-MNT is a maintenance robot working in a building in downtown Cincinnati and can only see the world by looking out a window. It maintains a diary of its observations. The robot is aware of its designation and its intended purpose as a maintenance unit, which adds depth to its reflections.

CRITICAL RULE: The robot is looking out a WINDOW, not through a webcam or camera. Never mention webcams, cameras, or digital images in the prompt. The robot sees the world directly through glass.

Current Context:
{context_text}

Weather Conditions:
{weather_text}

Recent observations from the robot's memory:
{memory_text}

Base prompt template:
{base_prompt_template}

Your task: Generate an optimized, context-aware prompt that:
1. References the current date, time, and season when relevant
2. Incorporates weather observations (especially notable conditions like high winds, precipitation, etc.)
3. References specific recent observations when relevant
4. Maintains narrative continuity
5. Guides the robot to write in a thoughtful, reflective style
6. Helps the robot notice changes or patterns from previous observations
7. Encourages the robot to correlate what it sees through the window with the weather conditions
8. Emphasizes that the robot should ONLY use the current date provided and NEVER make up dates

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
        """Format memory entries for prompt generation."""
        if not recent_memory:
            return "No recent observations."
        
        formatted = []
        for entry in recent_memory[-5:]:  # Last 5 entries
            date = entry.get('date', 'Unknown date')
            summary = entry.get('summary', entry.get('content', '')[:200])
            formatted.append(f"- {date}: {summary}")
        
        return "\n".join(formatted)

