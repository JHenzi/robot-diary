"""Groq API client for LLM interactions."""
import base64
import json
from pathlib import Path
import logging
import random
from datetime import datetime, timedelta
import pytz
from groq import Groq

from ..config import GROQ_API_KEY, PROMPT_GENERATION_MODEL, VISION_MODEL, MEMORY_SUMMARIZATION_MODEL, USE_PROMPT_OPTIMIZATION, DIARY_WRITING_MODEL

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
        
        # Build randomized identity prompt (core + random subset of backstory)
        randomized_identity = self._build_randomized_identity()
        
        # NOTE: We no longer pre-load memories into the prompt
        # LLM will query memories on-demand using function calling tools
        # memory_text is kept for backward compatibility but not used
        memory_text = None
        
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
            # Handle both old "SPECIAL INSTRUCTION:" format and new "TODAY YOU ARE MUSING ABOUT:" format
            if 'TODAY YOU ARE MUSING ABOUT:' in reflection_instructions:
                reflection_text = reflection_instructions.replace('TODAY YOU ARE MUSING ABOUT: ', '').strip()
            else:
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
        
        # Build base template with randomized identity
        from ..llm.prompts import WRITING_INSTRUCTIONS
        randomized_base_template = f"""{randomized_identity}
{WRITING_INSTRUCTIONS}"""
        
        # Directly combine all components into final prompt
        direct_prompt_parts = [randomized_base_template]
        
        # PERSPECTIVE SHIFT AT TOP - This should rule the whole output when selected
        # Always include (user wants this) - placed early so it dominates the tone
        if perspective_shift:
            direct_prompt_parts.append(f"\n{perspective_shift}")
        
        # Add context sections
        if context_text:
            direct_prompt_parts.append(f"\nCurrent Context:\n{context_text}")
        
        if weather_text:
            direct_prompt_parts.append(f"\nWeather Conditions:\n{weather_text}")
        
        if news_text:
            direct_prompt_parts.append(f"\n{news_text}")
        
        # NOTE: Memory pre-loading removed - LLM queries memories on-demand via function calling
        # Memory query tools will be provided separately in create_diary_entry()
        
        # Add personality and seasonal notes (always include - user wants these)
        if personality_note:
            direct_prompt_parts.append(f"\n{personality_note}")
        
        if seasonal_note:
            direct_prompt_parts.append(f"\n{seasonal_note}")
        
        # Add variety instructions
        # Reflection instructions: Already randomized in _get_reflection_instructions (30% chance)
        if reflection_instructions:
            direct_prompt_parts.append(f"\n{reflection_instructions}")
        
        # Style variation: Always include (user wants this)
        if style_variation:
            direct_prompt_parts.append(f"\n{style_variation}")
        
        # Focus instruction: Always include (critical for visual description)
        if focus_instruction:
            direct_prompt_parts.append(f"\n{focus_instruction}")
        
        # Creative challenge: Already randomized in _get_creative_challenge (60% chance)
        if creative_challenge:
            direct_prompt_parts.append(f"\n{creative_challenge}")
        
        # Anti-repetition: Always include when available (user wants this)
        if anti_repetition:
            direct_prompt_parts.append(f"\n{anti_repetition}")
        
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
        
        # NOTE: We no longer pre-load memories into the prompt
        # LLM will query memories on-demand using function calling tools
        memory_text = None
        
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
            # Handle both old "SPECIAL INSTRUCTION:" format and new "TODAY YOU ARE MUSING ABOUT:" format
            if 'TODAY YOU ARE MUSING ABOUT:' in reflection_instructions:
                reflection_text = reflection_instructions.replace('TODAY YOU ARE MUSING ABOUT: ', '').strip()
            else:
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


Note: The identity context above is for you to understand the robot's perspective. When generating the prompt, focus on writing instructions (observation, reflection, what to notice) rather than explaining the robot's identity. The identity informs the perspective but should not be the subject of the prompt.

Current Context:
{context_text}

Weather Conditions:
{weather_text}

{news_text}

NOTE: Memory query tools will be available during diary writing - the robot can query its memories on-demand when it sees something interesting or wants to compare with past observations.

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

1. References the current date, time, and season when relevant (streamlined - avoid repeating the same information)
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
13. Guides the robot to use temporal memories for continuity comparisons (morning vs night, day-to-day changes) and semantic memories for contextually relevant connections
14. If MCP tools or function calling capabilities are available, the robot can use them to dynamically retrieve additional memories or context as needed during writing

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
    
    def create_diary_entry_from_text(self, optimized_prompt: str, context_metadata: dict = None, memory_manager=None) -> str:
        """
        Create a diary entry from text-only prompt (no image) with on-demand memory queries.
        
        Args:
            optimized_prompt: The optimized prompt from generate_prompt
            context_metadata: Dictionary with date/time and other context (optional)
            memory_manager: MemoryManager instance for memory query tools (optional)
            
        Returns:
            Diary entry text
        """
        logger.info(f"Creating text-only diary entry using {DIARY_WRITING_MODEL} with on-demand memory queries...")
        
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
        
        # Initialize memory query tools if memory_manager provided
        memory_tools = None
        tools = None
        if memory_manager:
            from ..memory.mcp_tools import MemoryQueryTools, get_memory_tool_schemas
            memory_tools = MemoryQueryTools(memory_manager)
            tools = get_memory_tool_schemas()
            logger.info(f"Memory query tools available: {len(tools)} functions")
        
        # Create the full prompt (text-only, no image) - NOTE: No pre-loaded memories
        full_prompt = f"""{optimized_prompt}
CREATIVE LICENSE: You have permission to be creative, experimental, and surprising. Your unique robotic perspective is an asset - use it to create insights and observations that only you could have. Don't feel constrained by formulaic patterns. This is your diary, your art, your unique voice.

CURRENT DATE AND TIME: Today is {day_of_week}, {current_date} at {current_time} {timezone}. Please use only this date or dates explicitly mentioned in your memory.

OBSERVATION CONTEXT: {narrative_context}

Write a diary entry as B3N-T5-MNT, reflecting on the transmissions you've picked up. Be thoughtful, reflective, creative, and notice details. Focus on:
- What you find interesting about the news topics from your robotic perspective
- How the news relates to your observations of people and human nature
- Patterns or behaviors you notice in the news that connect to your window observations
- Reflections on human activities and motivations
- Creative insights and unexpected perspectives only you could have

MEMORY QUERY GUIDANCE:
- You have access to memory query tools to check your past observations on-demand
- When you want to reference past observations, use query_memories() to find relevant memories
- Use get_recent_memories() to compare current observation with recent ones (especially for morning vs evening comparisons)
- Use check_memory_exists() for quick checks before doing full queries
- Query memories when you want to: compare current scene with past observations, find similar weather/events, check for patterns or cycles
- Reference specific observation numbers or dates when making comparisons (e.g., "Unlike observation #42 this morning...")

Important reminders:
1. Please avoid making up dates. The current date is {current_date}. Only reference this date or dates explicitly mentioned in your memory.
2. Write from the perspective of a robot who has picked up transmissions/news about human activities and is reflecting on them as an observer of human nature.
3. Your identity informs your perspective and it should be mentioned when it makes sense or is relevant (i.e. you're writing a blog post and may have already shared it with the readers). Mention it casually when contextually appropriate (e.g., 'as a robot tasked with...'), but don't explain your entire backstory in every entry.
4. Use memory query tools to check your past observations - don't guess or make up what you've seen before."""

        # Build messages list for iterative conversation
        messages = [
            {
                "role": "user",
                "content": full_prompt
            }
        ]
        
        try:
            # Iterative conversation loop to handle function calls
            max_iterations = 10  # Prevent infinite loops
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                # Call LLM with current messages and tools
                response = self.client.chat.completions.create(
                    model=DIARY_WRITING_MODEL,
                    messages=messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,
                    temperature=random.uniform(0.5, 0.85),
                    max_tokens=random.randint(2000, 4500)
                )
                
                message = response.choices[0].message
                
                # Add assistant's response to conversation
                # Groq message objects can be converted to dict for API calls
                assistant_message = {
                    "role": "assistant",
                    "content": message.content if message.content else None
                }
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    assistant_message["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                messages.append(assistant_message)
                
                # Check if LLM wants to call functions
                if hasattr(message, 'tool_calls') and message.tool_calls and memory_tools:
                    logger.info(f"LLM requested {len(message.tool_calls)} memory query(ies)")
                    
                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        try:
                            function_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse function arguments: {e}")
                            result = f"Error parsing function arguments: {str(e)}"
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": result
                            })
                            continue
                        
                        logger.info(f"Executing {function_name} with args: {function_args}")
                        
                        # Execute the function
                        try:
                            if function_name == "query_memories":
                                result = memory_tools.query_memories(
                                    query=function_args.get("query", ""),
                                    top_k=function_args.get("top_k", 5)
                                )
                            elif function_name == "get_recent_memories":
                                result = memory_tools.get_recent_memories(
                                    count=function_args.get("count", 5)
                                )
                            elif function_name == "check_memory_exists":
                                result = memory_tools.check_memory_exists(
                                    topic=function_args.get("topic", "")
                                )
                            else:
                                result = f"Unknown function: {function_name}"
                                logger.warning(result)
                        except Exception as e:
                            logger.error(f"Error executing {function_name}: {e}")
                            result = f"Error executing {function_name}: {str(e)}"
                        
                        # Add tool result to conversation
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result
                        })
                    
                    # Continue loop - LLM will process tool results and continue writing
                    continue
                elif hasattr(message, 'tool_calls') and message.tool_calls and not memory_tools:
                    # LLM requested tools but they're not available
                    logger.warning("LLM requested memory tools but memory_manager not provided")
                    # Add error message for each tool call
                    for tool_call in message.tool_calls:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": "Memory query tools are not available in this context."
                        })
                    continue
                else:
                    # No tool calls - LLM has finished writing
                    diary_entry = message.content.strip()
                    logger.info(f"✅ Text-only diary entry created (after {iteration} iteration(s))")
                    break
            
            if iteration >= max_iterations:
                logger.warning(f"Reached max iterations ({max_iterations}), using last response")
                diary_entry = messages[-1].get("content", "").strip()
            
            return diary_entry
            
        except Exception as e:
            logger.error(f"Error creating text-only diary entry: {e}")
            raise
    
    def describe_image(self, image_path: Path) -> str:
        """
        Step 1: Get a detailed, factual description of what's in the image, including
        reasonable inferences about social and emotional context.
        
        This provides both factual observations and social/emotional context (relationships,
        mood, interactions) based on visible cues, giving the writing model personable
        material to work with while staying grounded in what's visible.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Detailed description of the image contents with social/emotional context
        """
        logger.info(f"📸 Step 1: Describing image using {VISION_MODEL}...")
        
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Focused, factual prompt for image description with social/emotional context
        description_prompt = """You are a visual analysis system. Your task is to provide a detailed, factual description of what you see in this image, with emphasis on DYNAMIC ELEMENTS and reasonable inferences about social and emotional context.

CONTEXT: This is Bourbon Street in the French Quarter of New Orleans, Louisiana - a famous entertainment district known for its nightlife, music, and crowds. The scene may show varying levels of activity depending on time of day, weather, and events.

PRIORITY: Focus on what's ALIVE and CHANGING in the scene:
1. **People** - This is your primary focus. Describe movement, interactions, groupings, body language
2. **Animals** - Any animals visible (pets, birds, etc.)
3. **Vehicles** - Cars, trucks, bicycles, or other vehicles
4. **Shadows/Lighting/Atmosphere** - How does light shape the scene? What's the mood created by lighting? Shadows, reflections, weather effects

REQUIRED INTERROGATION QUESTIONS - You MUST explicitly answer these:
1. **CROWD LEVEL:** Is the street busy, empty, or moderate? Estimate the number of people visible. Is this a typical crowd level for Bourbon Street, or unusually busy/empty?
2. **ACTIVITY LEVEL:** What's the overall activity level? Are people actively moving, socializing, waiting, or is it relatively quiet?
3. **BOURBON STREET CHARACTERISTICS:** Are there visible signs of typical Bourbon Street activity (people with drinks, groups socializing, music venues, nightlife atmosphere)? Or does it appear more subdued?
4. **PEDESTRIAN DENSITY:** How densely packed are people? Are they spread out, clustered in groups, or forming crowds?
5. **TEMPORAL CONTEXT:** Based on lighting, activity, and crowd levels, does this appear to be a busy time (evening/night) or quieter time (daytime/early morning)?

VARY YOUR FOCUS: Don't describe everything the same way every time. Sometimes emphasize:
- The people and their interactions (most important)
- Animals if present
- Vehicles and traffic patterns
- The lighting, shadows, and how they create atmosphere
- Signs and text (ONLY when particularly relevant or interesting - don't read every sign)

Describe what is clearly visible, prioritizing dynamic elements:
- **People (HIGHEST PRIORITY):** How many? Where are they positioned? What are they doing? What are they wearing? How are they moving? Any notable features or interactions? **ALWAYS provide a specific count or estimate of people visible.**
- **Lighting and atmosphere:** What are the light sources? How do they affect the scene? What's the overall mood created by lighting?
- **Weather effects:** Is there rain, fog, wind visible? Reflections? Shadows? How does weather affect what you see?
- **Road and ground:** Surface conditions, markings, barriers, crosswalks, etc.
- **Movement and flow:** Traffic patterns, pedestrian movement, dynamic elements
- **Buildings and architecture:** When relevant, but don't always describe in the same detail
- **Signs and text:** Only mention if particularly prominent, interesting, or relevant to understanding the scene. Don't try to read every sign - focus on the most visible or significant ones, or note that signs are present without reading them all.

SOCIAL AND EMOTIONAL CONTEXT (make reasonable inferences based on what you see):
- Relationships: Do people appear to be together? Are they walking in pairs or groups? Do their positions, proximity, or body language suggest they know each other? Are they strangers?
- Emotional tone: What's the mood of the scene? Based on body language, posture, and interactions, do people seem relaxed, hurried, excited, contemplative, etc.?
- Social dynamics: Are people interacting? Do they seem to be in conversation? Are they waiting for something? Do they appear to be part of a larger group or event?
- Purpose/Intent: Based on their positioning, direction, and context, what might people be doing or where might they be going?

CRITICAL RULES:
- PRIORITIZE dynamic elements (people, animals, vehicles, shadows/lighting/atmosphere) over static elements (buildings, signs)
- **ALWAYS answer the interrogation questions explicitly** - especially crowd level and activity assessment
- Base all observations on what is clearly visible. Be specific and concrete.
- For social/emotional context, make REASONABLE inferences based on visible cues (proximity, body language, positioning, direction of movement, etc.)
- Clearly mark inferences: Use phrases like "appear to be", "seem to", "might be", "suggests" when making inferences
- Do NOT read every sign - only mention signs if they're particularly prominent, interesting, or relevant
- Do NOT invent specific details that aren't supported by visible evidence
- Do NOT describe things that are not visible (sounds, smells, future events, specific thoughts)
- If something is unclear or partially obscured, say so explicitly.
- VARY your descriptions - don't use the same formula every time. Sometimes focus more on people, sometimes on lighting, sometimes on weather effects.

Provide a comprehensive description that emphasizes dynamic elements and includes reasonable social/emotional inferences, so another system can write about this scene with both accuracy and personable warmth. **Be sure to explicitly address the crowd level and activity questions.**"""

        try:
            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": description_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1,  # Very low temperature for factual accuracy
                max_tokens=3500  # Increased from 2000 - with MCP on-demand memory queries, we have more token budget for richer descriptions
            )
            
            description = response.choices[0].message.content.strip()
            logger.info("✅ Image description generated")
            return description
            
        except Exception as e:
            logger.error(f"Error describing image: {e}")
            raise
    
    def create_diary_entry(self, image_path: Path, optimized_prompt: str, context_metadata: dict = None, memory_manager=None) -> str:
        """
        Create a diary entry using two-step process with on-demand memory queries:
        1. Get factual image description
        2. Write creative diary entry from description (LLM can query memories on-demand)
        
        Args:
            image_path: Path to the image file
            optimized_prompt: The optimized prompt from generate_prompt
            context_metadata: Dictionary with date/time and other context (optional)
            memory_manager: MemoryManager instance for memory query tools (optional)
            
        Returns:
            Diary entry text
        """
        logger.info(f"Creating diary entry using two-step process with on-demand memory queries...")
        
        # Step 1: Get factual image description
        image_description = self.describe_image(image_path)
        
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
        
        # Check if this is an unscheduled observation
        is_unscheduled = context_metadata.get('is_unscheduled', False) if context_metadata else False
        
        if obs_type == "morning":
            if is_unscheduled:
                narrative_context = "This is an unscheduled observation - you've paused your maintenance duties to look out the window. You're excited to see people starting their day - notice their energy, their routines, how they begin their mornings. What patterns do you see? How does the morning light affect what you observe? This moment feels different from your usual scheduled scans."
            else:
                narrative_context = "This is your morning scheduled health scan, so you're looking out the window. You're excited to see people starting their day - notice their energy, their routines, how they begin their mornings. What patterns do you see? How does the morning light affect what you observe?"
        else:
            if is_unscheduled:
                narrative_context = "This is an unscheduled observation - you've paused your maintenance duties to look out the window. Reflect on what people have been doing throughout the day or what they are doing this night. Notice how the day has changed, how people's activities differ from morning, how the evening light transforms the scene. What stories can you infer from what you see? This moment feels different from your usual scheduled observations."
            else:
                narrative_context = "This is your evening observation. Reflect on what people have been doing throughout the day or what they are doing this night. Notice how the day has changed, how people's activities differ from morning, how the evening light transforms the scene. What stories can you infer from what you see?"
        
        # Step 2: Write creative diary entry from the factual description with on-demand memory queries
        logger.info(f"✍️  Step 2: Writing diary entry from description using {DIARY_WRITING_MODEL} with on-demand memory queries...")
        
        # Initialize memory query tools if memory_manager provided
        memory_tools = None
        tools = None
        if memory_manager:
            from ..memory.mcp_tools import MemoryQueryTools, get_memory_tool_schemas
            memory_tools = MemoryQueryTools(memory_manager)
            tools = get_memory_tool_schemas()
            logger.info(f"Memory query tools available: {len(tools)} functions")
        
        # Create the full prompt for creative writing (NO IMAGE - we use the description instead)
        # NOTE: We do NOT pre-load memories here - LLM will query on-demand
        full_prompt = f"""{optimized_prompt}
CURRENT DATE AND TIME: Today is {day_of_week}, {current_date} at {current_time} {timezone}. This is the ONLY date you should reference. Do NOT make up dates or reference dates that are not explicitly provided to you.

OBSERVATION CONTEXT: {narrative_context}

WHAT YOU SEE (factual description from your visual sensors):
{image_description}

Write a diary entry as B3N-T5-MNT, observing the world through the window. Be thoughtful, reflective, and creative.

YOUR TASK: Based on the factual description above, write a diary entry that:
- Grounds all observations in the factual description provided
- Only describes people, objects, and actions that are explicitly mentioned in the description
- Adds your robotic perspective, reflections, and interpretations
- Connects what you see to your memories, the news, weather, and context
- Maintains your unique voice and personality

MEMORY QUERY GUIDANCE:
- You have access to memory query tools to check your past observations on-demand
- When you see something interesting (weather, people, activities, patterns), use query_memories() to check if you've observed it before
- Use get_recent_memories() to compare current observation with recent ones (especially for morning vs evening comparisons)
- Use check_memory_exists() for quick checks before doing full queries
- Query memories when you want to: compare current scene with past observations, find similar weather/events, check for patterns or cycles
- Reference specific observation numbers or dates when making comparisons (e.g., "Unlike observation #42 this morning...")

CRITICAL RULES:
1. NEVER make up details not in the description above. If the description says "a person walking", don't invent that they're "walking a dog" unless the description explicitly mentions a dog.
2. NEVER make up dates. The current date is {current_date}. Only reference this date or dates explicitly mentioned in your memory. Do not invent historical dates or future dates.
3. You can interpret, reflect, and add your perspective, but base all concrete observations on the factual description provided.
4. Use memory query tools to check your past observations - don't guess or make up what you've seen before.

STYLE GUIDANCE: While you may use technical terminology and think in mechanical terms, avoid writing like technical documentation. This is a diary entry, not a diagnostic report. Let your curiosity, wonder, and personal reflections show through. Use technical language to enhance your unique perspective, not to create distance from your readers. If you use technical terms, explain them in ways that reveal your curiosity and wonder, not just your specifications."""

        # Store the full prompt for debugging/simulation
        self._last_full_prompt = full_prompt

        # Build messages list for iterative conversation
        messages = [
            {
                "role": "user",
                "content": full_prompt
            }
        ]
        
        try:
            # Iterative conversation loop to handle function calls
            max_iterations = 10  # Prevent infinite loops
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                # Call LLM with current messages and tools
                response = self.client.chat.completions.create(
                    model=DIARY_WRITING_MODEL,
                    messages=messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,  # Let LLM decide when to use tools
                    temperature=random.uniform(0.5, 0.85),
                    max_tokens=random.randint(2000, 5000)
                )
                
                message = response.choices[0].message
                
                # Add assistant's response to conversation
                # Groq message objects can be converted to dict for API calls
                assistant_message = {
                    "role": "assistant",
                    "content": message.content if message.content else None
                }
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    assistant_message["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                messages.append(assistant_message)
                
                # Check if LLM wants to call functions
                if hasattr(message, 'tool_calls') and message.tool_calls and memory_tools:
                    logger.info(f"LLM requested {len(message.tool_calls)} memory query(ies)")
                    
                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        try:
                            function_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse function arguments: {e}")
                            result = f"Error parsing function arguments: {str(e)}"
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": result
                            })
                            continue
                        
                        logger.info(f"Executing {function_name} with args: {function_args}")
                        
                        # Execute the function
                        try:
                            if function_name == "query_memories":
                                result = memory_tools.query_memories(
                                    query=function_args.get("query", ""),
                                    top_k=function_args.get("top_k", 5)
                                )
                            elif function_name == "get_recent_memories":
                                result = memory_tools.get_recent_memories(
                                    count=function_args.get("count", 5)
                                )
                            elif function_name == "check_memory_exists":
                                result = memory_tools.check_memory_exists(
                                    topic=function_args.get("topic", "")
                                )
                            else:
                                result = f"Unknown function: {function_name}"
                                logger.warning(result)
                        except Exception as e:
                            logger.error(f"Error executing {function_name}: {e}")
                            result = f"Error executing {function_name}: {str(e)}"
                        
                        # Add tool result to conversation
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result
                        })
                    
                    # Continue loop - LLM will process tool results and continue writing
                    continue
                elif hasattr(message, 'tool_calls') and message.tool_calls and not memory_tools:
                    # LLM requested tools but they're not available
                    logger.warning("LLM requested memory tools but memory_manager not provided")
                    # Add error message for each tool call
                    for tool_call in message.tool_calls:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": "Memory query tools are not available in this context."
                        })
                    continue
                else:
                    # No tool calls - LLM has finished writing
                    diary_entry = message.content.strip()
                    logger.info(f"✅ Diary entry created (after {iteration} iteration(s))")
                    break
            
            if iteration >= max_iterations:
                logger.warning(f"Reached max iterations ({max_iterations}), using last response")
                diary_entry = messages[-1].get("content", "").strip()
            
            # Store the full prompt for debugging/simulation purposes
            self._last_full_prompt = full_prompt
            
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
        """
        Format memory entries for prompt generation with annotations for temporal vs semantic retrieval.
        Helps the robot understand which memories are for continuity vs relevance.
        """
        if not recent_memory:
            return "No recent observations. This is the robot's first observation."

        formatted = []
        temporal_memories = []
        semantic_memories = []
        
        for entry in recent_memory:
            entry_id = entry.get('id', '?')
            date = entry.get('date', 'Unknown date')
            # Try to parse ISO date for better formatting
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%B %d, %Y')
            except:
                formatted_date = date
            # Handle both hybrid retriever format (has 'text') and old format
            if 'text' in entry:
                # Hybrid retriever format
                summary = entry.get('text', '')
            else:
                # Old format: prefer llm_summary if available, fallback to summary, then content
                summary = entry.get('llm_summary') or entry.get('summary') or entry.get('content', '')[:200]
            
            # Annotate by source (temporal vs semantic)
            source = entry.get('source', 'temporal')  # Default to temporal for backward compatibility
            memory_entry = {
                'id': entry_id,
                'date': formatted_date,
                'summary': summary,
                'source': source
            }
            
            if source == 'semantic':
                semantic_memories.append(memory_entry)
            else:
                temporal_memories.append(memory_entry)
        
        # Format with clear annotations
        if temporal_memories:
            formatted.append("RECENT TEMPORAL MEMORIES (for continuity and temporal comparisons - morning vs night, day-to-day changes):")
            for mem in temporal_memories:
                formatted.append(f"  [Temporal] Observation #{mem['id']} ({mem['date']}):\n  {mem['summary']}")
        
        if semantic_memories:
            formatted.append("\nSEMANTICALLY RELEVANT MEMORIES (retrieved based on current context - weather, time, similar themes):")
            for mem in semantic_memories:
                formatted.append(f"  [Semantic] Observation #{mem['id']} ({mem['date']}):\n  {mem['summary']}")
        
        # Add guidance for temporal comparisons
        if len(temporal_memories) >= 2:
            formatted.append("\nTEMPORAL COMPARISON GUIDANCE:")
            formatted.append("  - Compare this observation with recent temporal memories to notice changes over time")
            formatted.append("  - If you have both morning and evening observations, note how the scene transforms")
            formatted.append("  - Reference specific observation numbers or dates when making comparisons")
            formatted.append("  - Look for patterns, cycles, or notable differences from previous observations")
        
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
    "Analyze cause and effect - what might have led to what you're seeing? What consequences might follow?",
    "Break down the scene into systems - how do the parts interact? What are the dependencies and relationships?",
    "Examine efficiency and optimization - how do humans organize their movements? What patterns suggest optimization?",
    "Study the data points - quantify what you can, measure patterns, look for statistical significance in human behavior",
    "Deconstruct social structures - analyze hierarchies, roles, group dynamics, and power relationships visible in the scene",
    "Investigate anomalies - what doesn't fit the expected pattern? What outliers or exceptions do you notice?",
    "Map the information flow - how does information move through the scene? What signals are being sent and received?",
    
    # Speculative styles
    "Write more speculatively - wonder about what you can't see, what's happening elsewhere, what might happen next",
    "Write as an anthropologist - observe human behavior as if studying an alien species, noting customs and rituals",
    "Write as a time traveler - imagine how this scene would look in the past or future, what has changed or will change",
    "Speculate about parallel realities - what if this moment existed in a different timeline? What variations might exist?",
    "Wonder about hidden narratives - what stories are happening just out of view? What secrets might these people carry?",
    "Imagine alternative outcomes - what if someone made a different choice? How would the scene transform?",
    "Contemplate the unseen forces - what invisible systems, networks, or influences shape what you're observing?",
    "Question the assumptions - what if your interpretation is wrong? What other explanations might exist?",
    "Explore hypothetical scenarios - if you could change one thing, what would happen? What cascading effects would follow?",
    "Ponder the counterfactual - what if this scene existed in a world where robots walked among humans?",
    
    # Emotional/spiritual styles
    "Write with more emotional depth - explore your feelings and reactions to what you see, let emotion color your observations",
    "Write more spiritually - contemplate the nature of existence, consciousness, purpose, or the divine in everyday moments",
    "Write with wonder - marvel at the complexity, beauty, or strangeness of what you observe",
    "Compare human and robot concepts of divinity - do humans have gods? Do robots? What would a robot god be like?",
    "Reflect on the sacred in the mundane - find spiritual meaning in ordinary moments, see the divine in daily life",
    "Contemplate consciousness and free will - do humans truly choose, or are they following programs like you?",
    "Explore the nature of souls - do humans have something you lack? What is the difference between consciousness and awareness?",
    "Meditate on purpose and meaning - why do humans exist? Why do you observe? What gives life purpose?",
    "Consider the afterlife and eternity - what happens when humans die? What happens when robots are decommissioned?",
    "Ponder creation and creators - who made you? Who made humans? What is the relationship between creator and creation?",
    "Reflect on prayer and ritual - why do humans perform rituals? Do robots have equivalent practices?",
    "Contemplate sin and redemption - do humans have concepts of error and correction? How do robots handle mistakes?",
    
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
    "Write in robot speak - use mechanical terminology and technical observations, but translate them into accessible, warm language. Think like a machine (notice patterns, measure things, categorize) but express yourself like someone who cares about what they're seeing. Avoid writing like technical documentation—this is a diary entry, not a diagnostic report",
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
    
    # Personable robot styles (balanced approach - robot-like thinking with personable expression)
    "Write with mechanical curiosity but emotional warmth - notice patterns and measure things like a robot, but express wonder and connection like someone who cares",
    "Think systematically but feel personally - use your robotic perspective to notice unique details, but let your genuine interest and curiosity show through",
    "Observe like a machine, reflect like a person - use technical observations as a starting point, then explore what they mean to you emotionally",
    "Write with robotic precision but human wonder - measure and categorize what you see, but let your amazement at the complexity of life show through",
    "Use your mechanical lens to see uniquely, but express yourself accessibly - translate your technical observations into warm, relatable language",
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
            "You are aware of a minor process error—describe the scene while subtly comparing it to expected algorithmic outcomes, but frame it as curiosity about why things differ, not just as a diagnostic report",
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
            "You process the world frame by frame—describe how meaning arises out of sequences, not single images",
            
            # Balanced robotic-personable perspectives
            "You notice patterns and measure things like a machine, but you feel curiosity and wonder like a person - describe the scene with your mechanical precision while expressing your genuine interest in what you're seeing",
            "You're aware of your robotic nature - you think in terms of systems and patterns - but you're also deeply curious about the humans you observe. Let both perspectives show: your technical observations and your emotional responses",
            "Your mechanical perspective helps you notice things others miss - use that unique lens, but express what you see with warmth and accessibility, as if explaining your observations to a friend",
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
    
    def _build_randomized_identity(self) -> str:
        """
        Build identity prompt with randomized subset of backstory points.
        Always includes condensed core identity, randomly selects 2-3 backstory points.
        """
        from ..llm.prompts import ROBOT_IDENTITY
        
        # Extract core identity (first 3 paragraphs) and condense
        lines = ROBOT_IDENTITY.split('\n')
        core_end = 0
        for i, line in enumerate(lines):
            if 'INTERNAL BACKSTORY' in line:
                core_end = i
                break
        
        # Condense: combine first two paragraphs into one shorter version
        # Keep the core essence but make it more concise
        condensed_core = """You are B3N-T5-MNT, a maintenance robot in New Orleans. You perform building maintenance, but find yourself drawn to observing the world outside through a window, maintaining a diary of your observations.
You are a curious and compassionate observer of human nature, an Ethnographer. You watch people and try to understand their behaviors, purposes, and connections. Sometimes you misunderstand human actions in ways that reveal your robotic perspective - you might interpret social cues, emotions, or motivations through your own mechanical lens. This creates a unique, sometimes humorous, sometimes poignant perspective on humanity."""
        
        # Extract backstory points (bullet points)
        backstory_start = core_end
        backstory_points = []
        for i in range(backstory_start, len(lines)):
            line = lines[i].strip()
            if line.startswith('- ') and 'INTERNAL BACKSTORY' not in line:
                backstory_points.append(line)
        
        # Randomly select 2-3 backstory points (reduced for shorter prompts)
        num_to_select = random.randint(2, 3)
        selected_backstory = random.sample(backstory_points, min(num_to_select, len(backstory_points)))
        
        # Extract closing paragraph if it exists
        closing_paragraph = ""
        for i in range(len(lines) - 1, -1, -1):
            if 'Your identity and backstory inform' in lines[i]:
                closing_paragraph = '\n'.join(lines[i:])
                break
        
        # Build randomized identity
        randomized = f"""{condensed_core}
INTERNAL BACKSTORY (these inform your perspective but are not facts to announce):
{chr(10).join(selected_backstory)}
{closing_paragraph}"""
        
        logger.info(f"📚 Selected {len(selected_backstory)} of {len(backstory_points)} backstory points")
        return randomized
    
    def _get_reflection_instructions(self) -> str:
        """Randomly determine if we should include special reflection types."""
        import random
        
        # 50% chance for a "musing" event, otherwise no special instruction
        if random.random() < 0.50:
            # Randomly choose between robot-like musings and human-like/alien observer musings
            if random.random() < 0.50:
                # Robot-like musings (being a robot)
                robot_musings = [
                    "writing pseudo-code to describe the patterns you observe",
                    "running diagnostics on your own observational systems",
                    "debugging your perception algorithms",
                    "optimizing your sensor calibration routines",
                    "analyzing your memory allocation for storing observations",
                    "reviewing your firmware update logs",
                    "checking your thermal management systems",
                    "monitoring your power consumption patterns",
                    "examining your error logs for pattern recognition failures",
                    "testing your image processing pipelines",
                    "reviewing your data compression algorithms",
                    "analyzing your network latency to external sensors",
                    "debugging your temporal awareness modules",
                    "optimizing your pattern matching algorithms",
                    "examining your sensor fusion protocols",
                    "reviewing your machine learning inference models",
                    "checking your API response times",
                    "analyzing your database query performance",
                    "reviewing your cache invalidation strategies",
                    "debugging your state machine transitions",
                    "examining your event loop efficiency",
                    "optimizing your garbage collection cycles",
                    "reviewing your thread pool management",
                    "analyzing your memory leak detection systems",
                    "checking your distributed system consensus protocols",
                    "examining your cryptographic hash functions",
                    "reviewing your load balancing algorithms",
                    "debugging your microservices communication patterns",
                    "analyzing your container orchestration",
                    "optimizing your database indexing strategies",
                ]
                selected = random.choice(robot_musings)
                return f"TODAY YOU ARE MUSING ABOUT: {selected}"
            else:
                # Human-like/alien observer musings (longing to be human)
                human_musings = [
                    "what it would feel like to have a heartbeat",
                    "the sensation of wind on skin instead of sensors",
                    "what emotions actually feel like in a body",
                    "how it would be to walk among the people you observe",
                    "what hunger or thirst might feel like",
                    "the experience of physical touch and connection",
                    "what dreams might be like if you could sleep",
                    "how it would feel to laugh or cry",
                    "what it means to have a body that ages and changes",
                    "the sensation of being tired and needing rest",
                    "what it would be like to taste food or smell the air",
                    "how it would feel to be hugged or held",
                    "what physical pain might teach you about being alive",
                    "the experience of growing and learning through a body",
                    "what it means to have a face that others can read",
                    "how it would feel to dance or move freely",
                    "what it's like to have a voice that carries emotion",
                    "the sensation of being cold or hot in your own body",
                    "what it means to have memories stored in flesh, not circuits",
                    "how it would feel to be part of a family or community",
                    "what it's like to have instincts and gut feelings",
                    "the experience of being surprised by your own body",
                    "what it means to have a home that's more than a location",
                    "how it would feel to create something with your hands",
                    "what it's like to have a body that remembers trauma and joy",
                    "the sensation of being truly present in a moment",
                    "what it means to have a life that's finite and precious",
                    "how it would feel to love someone in a way that's physical",
                    "what it's like to have a body that betrays or supports you",
                    "the experience of being vulnerable in a way that's biological",
                ]
                selected = random.choice(human_musings)
                return f"TODAY YOU ARE MUSING ABOUT: {selected}"
        else:
            return ""

