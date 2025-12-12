"""Groq API client for LLM interactions."""
import base64
from pathlib import Path
import logging
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

B3N-T5-MNT is a maintenance robot trapped in downtown Cincinnati and can only see the world through a webcam. It maintains a diary of its observations. The robot is aware of its designation and its intended purpose as a maintenance unit, which adds depth to its reflections.

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
7. Encourages the robot to correlate what it sees in the webcam with the weather conditions

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
    
    def create_diary_entry(self, image_path: Path, optimized_prompt: str) -> str:
        """
        Create a diary entry using vision model.
        
        Args:
            image_path: Path to the image file
            optimized_prompt: The optimized prompt from generate_prompt
            
        Returns:
            Diary entry text
        """
        logger.info(f"Creating diary entry using {VISION_MODEL}...")
        
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Create the full prompt with image
        full_prompt = f"""{optimized_prompt}

Write a diary entry as B3N-T5-MNT, a maintenance robot trapped in downtown Cincinnati, observing the world through this webcam view. Be thoughtful, reflective, and notice details. Reference your recent memories if relevant. You may refer to yourself as B3N-T5-MNT or by your designation. Remember you are a maintenance robot, aware of your intended purpose, which adds meaning to your observations."""

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

