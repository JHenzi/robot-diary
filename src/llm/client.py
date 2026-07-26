"""Groq API client for LLM interactions."""
import base64
import json
from pathlib import Path
import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional
import pytz
from groq import Groq

from ..config import GROQ_API_KEY, PROMPT_GENERATION_MODEL, VISION_MODEL, MEMORY_SUMMARIZATION_MODEL, USE_PROMPT_OPTIMIZATION, DIARY_WRITING_MODEL

logger = logging.getLogger(__name__)


class GroqClient:
    """Client for interacting with Groq API."""
    
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
    
    def _get_reasoning_params(self, model: str) -> dict:
        """Get reasoning parameters if model is GPT-OSS."""
        if "gpt-oss" in model.lower():
            return {
                "reasoning_effort": "medium",  # Use reasoning_effort for Chat Completions API
                "reasoning_format": "hidden"  # Hide reasoning steps from output
            }
        return {}
    
    def generate_direct_prompt(self, recent_memory: list[dict], base_prompt_template: str,
                              context_metadata: dict = None, weather_data: dict = None,
                              memory_count: int = 0, days_since_first: int = 0, 
                              boredom_directive: Optional[str] = None) -> str:
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
            reception = self._get_news_reception_mode()
            logger.info(f"📻 News reception mode: {reception['name']}")
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
                news_text = (
                    f"{reception['intro']}: {', '.join(article_refs)}. "
                    f"{reception['instructions']} Consider the timing of when these events happened."
                )
            elif context_metadata.get('news_headlines'):
                # Fallback to headlines only
                headlines = context_metadata['news_headlines']
                if headlines:
                    news_text = (
                        f"{reception['intro']}: {', '.join(headlines)}. "
                        f"{reception['instructions']}"
                    )

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
        focus_text = focus_instruction.replace('FOCUS: ', '').strip()
        logger.info(f"🎯 Selected focus: {focus_text}")

        emotional_state = self._get_emotional_state()
        if emotional_state:
            emotional_text = emotional_state.replace('EMOTIONAL STATE: ', '').strip()
            logger.info(f"💔 Emotional state: {emotional_text[:80]}{'...' if len(emotional_text) > 80 else ''}")
        else:
            logger.info("💔 Emotional state: nominal")

        # Structural template - when dominant, it suppresses style and focus so the
        # model commits to one form instead of averaging many instructions into a report
        structure_instruction, structure_dominant = self._get_structure_instruction()
        if structure_instruction:
            structure_text = structure_instruction.replace('STRUCTURE: ', '').strip()
            logger.info(f"🏗️  Structure: {structure_text[:80]}{'...' if len(structure_text) > 80 else ''}")
            if structure_dominant:
                logger.info("🏗️  Structure is DOMINANT - suppressing style and focus instructions this run")
                style_variation = ""
                focus_instruction = ""
        else:
            logger.info("🏗️  No structure template selected")

        # Log a summary of all prompt selections
        logger.info("=" * 60)
        logger.info("📝 PROMPT SELECTIONS SUMMARY:")
        logger.info(f"   🤖 Personality: {personality_text[:80]}{'...' if len(personality_text) > 80 else ''}")
        if seasonal_note:
            logger.info(f"   🍂 Seasonal: {seasonal_text[:80]}{'...' if len(seasonal_text) > 80 else ''}")
        if reflection_instructions:
            if 'TODAY YOU ARE MUSING ABOUT:' in reflection_instructions:
                reflection_text = reflection_instructions.replace('TODAY YOU ARE MUSING ABOUT: ', '').strip()
            else:
                reflection_text = reflection_instructions.replace('SPECIAL INSTRUCTION: ', '').strip()
            logger.info(f"   💭 Reflection: {reflection_text[:80]}{'...' if len(reflection_text) > 80 else ''}")
        style_line = style_variation.split('\n')[-1].strip('- ').strip() if style_variation else ''
        logger.info(f"   🎨 Style: {style_line[:80]}")
        if structure_instruction:
            logger.info(f"   🏗️  Structure: {structure_text[:80]}{'...' if len(structure_text) > 80 else ''}")
        logger.info(f"   👁️  Perspective: {perspective_text[:80]}{'...' if len(perspective_text) > 80 else ''}")
        logger.info(f"   🎯 Focus: {focus_text[:80]}{'...' if len(focus_text) > 80 else ''}")
        if emotional_state:
            logger.info(f"   💔 Emotional: {emotional_text[:80]}{'...' if len(emotional_text) > 80 else ''}")
        logger.info("=" * 60)

        # Build base template with randomized identity
        from ..llm.prompts import WRITING_INSTRUCTIONS
        randomized_base_template = f"""{randomized_identity}
{WRITING_INSTRUCTIONS}"""

        # Directly combine all components into final prompt
        direct_prompt_parts = [randomized_base_template]

        # EMOTIONAL STATE - inject first so it colours the entire entry
        if emotional_state:
            direct_prompt_parts.append(f"\n{emotional_state}")

        # PERSPECTIVE SHIFT - placed early so it dominates tone
        if perspective_shift:
            direct_prompt_parts.append(f"\n{perspective_shift}")

        # BOREDOM DIRECTIVE
        if boredom_directive:
            direct_prompt_parts.append(f"\n{boredom_directive}")

        # Context sections
        if context_text:
            direct_prompt_parts.append(f"\nCurrent Context:\n{context_text}")
        if weather_text:
            direct_prompt_parts.append(f"\nWeather Conditions:\n{weather_text}")
        if news_text:
            direct_prompt_parts.append(f"\n{news_text}")

        # Identity reinforcement
        if personality_note:
            direct_prompt_parts.append(f"\n{personality_note}")
        if seasonal_note:
            direct_prompt_parts.append(f"\n{seasonal_note}")

        # Variety modifiers
        if reflection_instructions:
            direct_prompt_parts.append(f"\n{reflection_instructions}")
        if structure_instruction:
            direct_prompt_parts.append(f"\n{structure_instruction}")
        if style_variation:
            direct_prompt_parts.append(f"\n{style_variation}")
        if focus_instruction:
            direct_prompt_parts.append(f"\n{focus_instruction}")

        final_prompt = "\n".join(direct_prompt_parts)
        logger.info("✅ Direct prompt generated")
        return final_prompt
    
    def generate_prompt(self, recent_memory: list[dict], base_prompt_template: str, 
                       context_metadata: dict = None, weather_data: dict = None, 
                       memory_count: int = 0, days_since_first: int = 0,
                       boredom_directive: Optional[str] = None) -> str:
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
                                             context_metadata, weather_data, memory_count, days_since_first,
                                             boredom_directive=boredom_directive)
        
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
            reception = self._get_news_reception_mode()
            logger.info(f"📻 News reception mode: {reception['name']}")
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
                news_text = (
                    f"{reception['intro']}: {', '.join(article_refs)}. "
                    f"{reception['instructions']} Consider the timing of when these events happened."
                )
            elif context_metadata.get('news_headlines'):
                # Fallback to headlines only
                headlines = context_metadata['news_headlines']
                if headlines:
                    news_text = (
                        f"{reception['intro']}: {', '.join(headlines)}. "
                        f"{reception['instructions']}"
                    )

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
        focus_text = focus_instruction.replace('FOCUS: ', '').strip()
        logger.info(f"🎯 Selected focus: {focus_text}")

        emotional_state = self._get_emotional_state()
        if emotional_state:
            emotional_text = emotional_state.replace('EMOTIONAL STATE: ', '').strip()
            logger.info(f"💔 Emotional state: {emotional_text[:80]}{'...' if len(emotional_text) > 80 else ''}")
        else:
            logger.info("💔 Emotional state: nominal")

        # Log a summary of all prompt selections
        logger.info("=" * 60)
        logger.info("📝 PROMPT SELECTIONS SUMMARY:")
        logger.info(f"   🤖 Personality: {personality_text[:80]}{'...' if len(personality_text) > 80 else ''}")
        if seasonal_note:
            logger.info(f"   🍂 Seasonal: {seasonal_text[:80]}{'...' if len(seasonal_text) > 80 else ''}")
        if reflection_instructions:
            if 'TODAY YOU ARE MUSING ABOUT:' in reflection_instructions:
                reflection_text = reflection_instructions.replace('TODAY YOU ARE MUSING ABOUT: ', '').strip()
            else:
                reflection_text = reflection_instructions.replace('SPECIAL INSTRUCTION: ', '').strip()
            logger.info(f"   💭 Reflection: {reflection_text[:80]}{'...' if len(reflection_text) > 80 else ''}")
        style_line = style_variation.split('\n')[-1].strip('- ').strip() if style_variation else ''
        logger.info(f"   🎨 Style: {style_line[:80]}")
        logger.info(f"   👁️  Perspective: {perspective_text[:80]}{'...' if len(perspective_text) > 80 else ''}")
        logger.info(f"   🎯 Focus: {focus_text[:80]}{'...' if len(focus_text) > 80 else ''}")
        if emotional_state:
            logger.info(f"   💔 Emotional: {emotional_text[:80]}{'...' if len(emotional_text) > 80 else ''}")
        logger.info("=" * 60)

        prompt_gen_prompt = f"""You are helping to generate an optimized prompt for a diary-writing maintenance robot named B3N-T5-MNT.

IDENTITY CONTEXT (for your understanding, not to repeat in the prompt):
B3N-T5-MNT is a maintenance robot working in a building in New Orleans, Louisiana. It performs building maintenance and repair tasks. The robot's owners are kind and treat it well - it is not a slave, but rather maladjusted to its situation. It finds itself drawn to observing the world outside through a window, maintaining a diary of its observations. The robot is an observer of human nature with a unique robotic perspective.

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

{emotional_state}

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
        tools = []
        if memory_manager:
            from ..memory.mcp_tools import MemoryQueryTools, get_memory_tool_schemas
            memory_tools = MemoryQueryTools(memory_manager)
            tools.extend(get_memory_tool_schemas())
            logger.info(f"Memory query tools available: {len(get_memory_tool_schemas())} functions")
        
        # Browser search is a built-in Groq tool for GPT-OSS-120B
        # We don't need to add it to the tools list - it's automatically available
        # Just log that it's available
        from ..config import ENABLE_WEB_SEARCH
        if ENABLE_WEB_SEARCH and self._supports_browser_search():
            logger.info("🌐 Browser search tool available - robot can search the web for current information (built-in Groq tool)")
        
        # Set tools to None if empty (for API compatibility)
        if not tools:
            tools = None
        
        # Generate randomized search suggestions (only if web search is enabled)
        search_suggestions = []
        web_search_guidance = ""
        if ENABLE_WEB_SEARCH and self._supports_browser_search():
            search_suggestions = self._get_randomized_search_suggestions(context_metadata)
            search_suggestions_text = ""
            if search_suggestions:
                suggestions_list = "\n".join([f"- {suggestion}" for suggestion in search_suggestions])
                search_suggestions_text = f"\n\nSUGGESTED SEARCH TOPICS (you can search for these or anything else you're curious about):\n{suggestions_list}"
            
            web_search_guidance = f"""
WEB SEARCH GUIDANCE:
- You have access to browser_search() to search the web for current information
- **IMPORTANT: Do NOT search for weather information** - weather data is already provided in your context, so searching for it would be redundant
- Use web search when you're curious about something you observe or need context for your observations
- Search for: New Orleans events and happenings for today's date ({current_date}), local news that might explain what you see, holiday-specific events or traditions, or anything else that might help you understand what you're observing
- You can search for the suggested topics below, or anything else you're curious about (but not weather)
- Web search results can provide valuable context - incorporate them naturally into your observations{search_suggestions_text}
"""
        
        # Create the full prompt (text-only, no image) - NOTE: No pre-loaded memories
        full_prompt = f"""{optimized_prompt}
CURRENT DATE AND TIME: Today is {day_of_week}, {current_date} at {current_time} {timezone}. This is the ONLY date you should reference. Do NOT make up dates or reference dates that are not explicitly provided to you.

OBSERVATION CONTEXT: {narrative_context}

Write a diary entry as B3N-T5-MNT, reflecting on the transmissions you've picked up. Be thoughtful, reflective, and true to your voice.

MEMORY QUERY GUIDANCE:
- Use query_memories() to find past entries matching a named person, place, or topic you hear about
- Use get_recent_memories() to compare this moment with recent entries
- Reference specific observation numbers when making comparisons
- If a query returns no good match, do not force a parallel - the absence of a memory is itself worth noting
{web_search_guidance}

CRITICAL RULES:
1. NEVER make up dates. Current date: {current_date}. Only reference this date or dates from your memory.
2. Mention your identity casually when contextually appropriate — don't explain your backstory in every entry.
3. Use memory query tools rather than guessing what you've seen before."""

        # Freshness directives (no image description in the text-only path, so all
        # overused phrases except scene objects are eligible for the ban list)
        from .freshness import get_freshness_directives
        from ..config import HUGO_CONTENT_DIR
        freshness_directives = get_freshness_directives(HUGO_CONTENT_DIR)
        if freshness_directives:
            full_prompt += f"\n\n{freshness_directives}"

        # 1 in 10 chance: ask the robot to mention The Henzi Foundation and urge donation
        henzi_note = self._get_henzi_prompt_addition()
        if henzi_note:
            full_prompt += henzi_note
            logger.info("🎗️ Henzi Foundation mention included in this prompt (10% roll)")

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
            truncation_retried = False  # Per-entry: retry once if the model gets cut off mid-entry

            while iteration < max_iterations:
                iteration += 1

                # Call LLM with current messages and tools
                reasoning_params = self._get_reasoning_params(DIARY_WRITING_MODEL)
                response = self.client.chat.completions.create(
                    model=DIARY_WRITING_MODEL,
                    messages=messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,
                    temperature=random.uniform(0.5, 0.85),
                    max_tokens=random.randint(4000, 7000) if truncation_retried else random.randint(800, 4500),
                    **reasoning_params  # Unpack reasoning params if GPT-OSS
                )

                message = response.choices[0].message
                finish_reason = getattr(response.choices[0], "finish_reason", None)

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
                                "name": tc.function.name.replace("functions/", "", 1) if tc.function.name.startswith("functions/") else tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                messages.append(assistant_message)

                # Check if LLM wants to call functions
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    # Log browser search calls (browser.search is a built-in Groq tool, handled automatically)
                    browser_search_calls = [tc for tc in message.tool_calls if (tc.function.name.replace("functions/", "", 1) if tc.function.name.startswith("functions/") else tc.function.name) in ["browser_search", "browser.search"]]
                    if browser_search_calls:
                        for tc in browser_search_calls:
                            try:
                                search_args = json.loads(tc.function.arguments)
                                search_query = search_args.get("query", "")
                                logger.info(f"🌐 Robot requested web search: '{search_query}'")
                            except:
                                logger.info("🌐 Robot requested web search (query parsing failed)")
                    
                    # Handle memory tool calls
                    if memory_tools:
                        memory_tool_calls = [tc for tc in message.tool_calls if (tc.function.name.replace("functions/", "", 1) if tc.function.name.startswith("functions/") else tc.function.name) in ["query_memories", "get_recent_memories", "check_memory_exists"]]
                        if memory_tool_calls:
                            logger.info(f"LLM requested {len(memory_tool_calls)} memory query(ies)")
                            
                            # Execute each memory tool call
                            for tool_call in memory_tool_calls:
                                function_name = tool_call.function.name
                                # Normalize function name - some models add "functions/" prefix
                                if function_name.startswith("functions/"):
                                    function_name = function_name.replace("functions/", "", 1)
                                    logger.debug(f"Normalized function name from '{tool_call.function.name}' to '{function_name}'")
                                
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
                    
                    # Note: browser_search results are automatically handled by Groq API
                    # The API will add tool results for browser_search automatically
                    
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
                    diary_entry = (message.content or "").strip()
                    if not diary_entry:
                        logger.warning(
                            "LLM returned an empty text-only diary entry (no tool calls). "
                            "Retrying with an explicit instruction to output the entry text."
                        )
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "Please output the full diary entry text now. "
                                    "Do not call any tools. Do not return an empty response."
                                ),
                            }
                        )
                        continue

                    if finish_reason == "length" and not truncation_retried:
                        truncation_retried = True
                        logger.warning(
                            f"Text-only diary entry was cut off by max_tokens ({len(diary_entry)} chars). "
                            "Retrying once with a larger token budget."
                        )
                        messages.pop()  # discard the truncated draft
                        messages.append({
                            "role": "user",
                            "content": (
                                "Your previous response was cut off before it finished. Write the complete "
                                "diary entry again from the start, in full, ending on a finished thought."
                            ),
                        })
                        continue

                    logger.info(f"✅ Text-only diary entry created (after {iteration} iteration(s))")
                    break
            
            if iteration >= max_iterations:
                logger.warning(f"Reached max iterations ({max_iterations}), using last response")
                diary_entry = (messages[-1].get("content") or "").strip()
            
            return diary_entry
            
        except Exception as e:
            logger.error(f"Error creating text-only diary entry: {e}")
            raise
    
    def describe_image(self, image_path: Path, boredom_directive: Optional[str] = None) -> str:
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
        
        # Focused, factual prompt for image description: SCENE first, then details (including human count).
        description_prompt = """You are a visual analysis system. Your task is to provide (1) a high-level SCENE description that captures the moment and mood, then (2) a detailed, factual description with emphasis on dynamic elements and reasonable social/emotional inferences.

CONTEXT: This is Bourbon Street in the French Quarter of New Orleans, Louisiana - a famous entertainment district known for its nightlife, music, and crowds. The scene may show varying levels of activity depending on time of day, weather, and events.

---

PART 1 — DESCRIBE THE SCENE (required, first):

Before any details, write 1–3 sentences that answer: **What kind of moment is this?** Include:
- **The scene as a whole**: e.g. "A quiet, sunlit morning with a few figures and long shadows—like a paused frame" or "A lively street scene at dusk, bustling with pedestrians and neon."
- **Overall mood and time-of-day feel**: tranquil, bustling, post-rain calm, evening transition, etc.
- **The 'story' of the frame**: what a viewer would feel at a glance (e.g. "a busy, yet momentarily calm, urban environment" or "vibrant, active atmosphere").

This scene summary is the anchor. The next part fills in specifics.

---

PART 2 — DETAILED DESCRIPTION (after the scene summary):

**Human count (required):** State how many humans are visible (e.g. "There are 12 humans visible" or "Two humans"). Keep this explicit—it is used downstream.

**Priority — focus on what's ALIVE and CHANGING:**
1. **People** - Count, positions, movement, interactions, groupings, body language, clothing when notable.
2. **Animals** - Any animals visible (pets, birds, etc.).
3. **Vehicles** - Cars, trucks, bicycles, golf carts, etc.
4. **Shadows/Lighting/Atmosphere** - How light shapes the scene; mood from lighting; shadows, reflections, weather effects.

**Required interrogation (answer explicitly):**
1. **CROWD LEVEL:** Busy, empty, or moderate? Typical for Bourbon Street or unusually so?
2. **ACTIVITY LEVEL:** Actively moving/socializing, waiting, or relatively quiet?
3. **BOURBON STREET CHARACTERISTICS:** Signs of typical nightlife (drinks, groups, music venues) or more subdued?
4. **PEDESTRIAN DENSITY:** Spread out, clustered, or forming crowds?
5. **TEMPORAL CONTEXT:** Busy time (evening/night) or quieter time (daytime/early morning)?

**Then describe, as relevant:**
- **People:** Where positioned, what they're doing, wearing, how they're moving; notable interactions. (Human count already stated above.)
- **Lighting and atmosphere:** Light sources, effect on scene, overall mood from lighting.
- **Weather effects:** Rain, fog, wind, reflections, shadows.
- **Road and ground:** Surface, markings, barriers, crosswalks.
- **Movement and flow:** Traffic patterns, pedestrian flow.
- **Buildings and architecture:** When relevant; don't repeat the same level of detail every time.
- **Signs and text:** Only if prominent or relevant; don't read every sign.

**SOCIAL AND EMOTIONAL CONTEXT (required — make reasonable inferences from visible cues):**

This is important for downstream writing. Based on what you see (proximity, body language, direction of movement, groupings, posture), describe:

1. **Relationships:** Do people appear to be together or strangers? Walking in pairs or groups? Does their body language (facing each other, shared pace, gestures) suggest they know each other? Any family, friends, or solo figures?
2. **Emotional tone:** What's the mood of the scene? Do people seem relaxed, hurried, excited, contemplative, bored, alert? What in their posture, gait, or positioning suggests this?
3. **Social dynamics:** Are people interacting—in conversation, waiting together, or moving independently? Do any seem to be part of a larger group or event (e.g. a crowd watching something, a tour, a queue)? Any sense of connection or isolation?
4. **Purpose or intent:** Based on positioning, direction, and context, what might people be doing or where might they be going? (e.g. heading into a venue, crossing the street with purpose, lingering, people-watching.)

Use phrases like "appear to be", "seem to", "might be", "suggests" when inferring. Be concrete—point to visible cues that support your reading. This gives the diary writer material for personable, observant prose.

---

CRITICAL RULES:
- **Always output PART 1 (scene) first**, then PART 2 (details). Both are required.
- **Always state human count explicitly** in PART 2.
- **Always include the SOCIAL AND EMOTIONAL CONTEXT** section—relationships, emotional tone, social dynamics, and purpose/intent—so the diary can write with personable warmth.
- Base everything on what is clearly visible; be specific and concrete.
- Mark inferences with "appear to be", "seem to", "might be", "suggests".
- Do NOT read every sign; only mention prominent or relevant ones.
- Do NOT invent details unsupported by the image.
- Do NOT describe non-visible things (sounds, smells, future events, inner thoughts).
- If something is unclear or partially obscured, say so.
- VARY your descriptions—sometimes emphasize people, sometimes lighting, sometimes weather.

Provide the scene summary first, then a comprehensive detailed description, so another system can write about this moment with both a clear sense of the scene and accurate, personable detail."""
        
        # Inject boredom directive if provided
        if boredom_directive:
            # Adapt directive for image analysis context
            image_analysis_directive = boredom_directive.replace("DISREGARD THE MUNDANE", "FOCUS ON MICROSCOPIC DETAILS").replace("DOCUMENT THE ANOMALY", "FOCUS ON NOVEL ELEMENTS")
            description_prompt += f"\n\n{image_analysis_directive}\n"

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
                temperature=0.1 if random.random() < 0.5 else round(random.uniform(0.2, 0.5), 2),  # Default low for accuracy, sometimes higher for richer language
                max_tokens=3500  # Increased from 2000 - with MCP on-demand memory queries, we have more token budget for richer descriptions
            )
            
            description = response.choices[0].message.content.strip()
            logger.info("✅ Image description generated")
            return description
            
        except Exception as e:
            logger.error(f"Error describing image: {e}")
            raise
    
    def create_diary_entry(self, image_path: Path, optimized_prompt: str, context_metadata: dict = None, memory_manager=None, boredom_directive: Optional[str] = None) -> str:
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
        image_description = self.describe_image(image_path, boredom_directive=boredom_directive)
        
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
        tools = []
        if memory_manager:
            from ..memory.mcp_tools import MemoryQueryTools, get_memory_tool_schemas
            memory_tools = MemoryQueryTools(memory_manager)
            # Use tool names as-is (query_memories, get_recent_memories, check_memory_exists). Do NOT
            # add "functions/" prefix: on follow-up turns the model often returns names without the
            # prefix, causing "tool 'query_memories' which was not in request.tools" and a retry without tools.
            tools.extend(get_memory_tool_schemas())
            logger.info(f"Memory query tools available: {len(get_memory_tool_schemas())} functions")
        
        # Browser search is a built-in Groq tool for GPT-OSS-120B
        # We don't need to add it to the tools list - it's automatically available
        # Just log that it's available
        from ..config import ENABLE_WEB_SEARCH
        if ENABLE_WEB_SEARCH and self._supports_browser_search():
            logger.info("🌐 Browser search tool available - robot can search the web for current information (built-in Groq tool)")
        
        # Set tools to None if empty (for API compatibility)
        if not tools:
            tools = None
        
        # Generate randomized search suggestions (only if web search is enabled)
        search_suggestions = []
        web_search_guidance = ""
        from ..config import ENABLE_WEB_SEARCH
        if ENABLE_WEB_SEARCH and self._supports_browser_search():
            search_suggestions = self._get_randomized_search_suggestions(context_metadata)
            search_suggestions_text = ""
            if search_suggestions:
                suggestions_list = "\n".join([f"- {suggestion}" for suggestion in search_suggestions])
                search_suggestions_text = f"\n\nSUGGESTED SEARCH TOPICS (you can search for these or anything else you're curious about):\n{suggestions_list}"
            
            web_search_guidance = f"""
WEB SEARCH GUIDANCE:
- You have access to browser_search() to search the web for current information
- **IMPORTANT: Do NOT search for weather information** - weather data is already provided in your context, so searching for it would be redundant
- Use web search when you're curious about something you observe or need context for your observations
- Search for: New Orleans events and happenings for today's date ({current_date}), local news that might explain what you see, holiday-specific events or traditions, or anything else that might help you understand what you're observing
- You can search for the suggested topics below, or anything else you're curious about (but not weather)
- Web search results can provide valuable context - incorporate them naturally into your observations{search_suggestions_text}
"""
        
        # Create the full prompt for creative writing (NO IMAGE - we use the description instead)
        # NOTE: We do NOT pre-load memories here - LLM will query on-demand
        full_prompt = f"""{optimized_prompt}
CURRENT DATE AND TIME: Today is {day_of_week}, {current_date} at {current_time} {timezone}. This is the ONLY date you should reference. Do NOT make up dates or reference dates that are not explicitly provided to you.

OBSERVATION CONTEXT: {narrative_context}

WHAT YOU SEE (factual description from your visual sensors):
{image_description}

Write a diary entry as B3N-T5-MNT. Base all concrete observations on the factual description provided — do not invent details not mentioned there. Be thoughtful, reflective, and true to your voice.

MEMORY QUERY GUIDANCE:
- Use query_memories() to find past observations matching a key detail you notice (object, clothing, group size, weather, news topic)
- Use get_recent_memories() to compare this moment with recent entries
- Reference specific observation numbers when making comparisons
- If a query returns no good match, do not force a parallel - the absence of a memory is itself worth noting
{web_search_guidance}

CRITICAL RULES:
1. NEVER invent details not in the description above.
2. NEVER make up dates. Current date: {current_date}. Only reference this date or dates from your memory.
3. Use memory query tools rather than guessing what you've seen before.
4. The factual description above is scratch material for you alone - it is not a template. NEVER reuse its labels, bold headers, or field names (e.g. "Human count", "Required interrogation", "Crowd level", "Priority - Alive/Changing") in your diary entry, and never structure your entry as a form, checklist, or report answering those questions in order. Write in your own flowing voice; if a structure directive above tells you to do otherwise, that directive wins - but plain prose is the default."""

        # Freshness directives: locally-computed from recent published entries.
        # Bans recurring language tics; recurring real-world fixtures (present in
        # today's image description) are never banned, only treated differently.
        from .freshness import get_freshness_directives
        from ..config import HUGO_CONTENT_DIR
        freshness_directives = get_freshness_directives(HUGO_CONTENT_DIR, image_description=image_description)
        if freshness_directives:
            full_prompt += f"\n\n{freshness_directives}"

        # 1 in 10 chance: ask the robot to mention The Henzi Foundation and urge donation
        henzi_note = self._get_henzi_prompt_addition()
        if henzi_note:
            full_prompt += henzi_note
            logger.info("🎗️ Henzi Foundation mention included in this prompt (10% roll)")

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
            tool_validation_retried = False  # Per-entry: retry same request once on tool validation error
            truncation_retried = False  # Per-entry: retry once if the model gets cut off mid-entry

            while iteration < max_iterations:
                iteration += 1

                # Call LLM with current messages and tools
                try:
                    reasoning_params = self._get_reasoning_params(DIARY_WRITING_MODEL)
                    response = self.client.chat.completions.create(
                        model=DIARY_WRITING_MODEL,
                        messages=messages,
                        tools=tools if tools else None,
                        tool_choice="auto" if tools else None,  # Let LLM decide when to use tools
                        temperature=random.uniform(0.5, 0.85),
                        max_tokens=random.randint(4500, 7000) if truncation_retried else random.randint(800, 5000),
                        **reasoning_params  # Unpack reasoning params if GPT-OSS
                    )
                except Exception as e:
                    error_str = str(e)
                    # Handle tool call validation errors (e.g. "tool 'X' which was not in request.tools")
                    # Often happens on follow-up turns if API/model disagree on tool names. Try same request once, then give up tools.
                    if "tool call validation failed" in error_str.lower() or "which was not in request.tools" in error_str.lower() or "tool choice is none" in error_str.lower():
                        # First try: retry the exact same request once (in case of transient API quirk)
                        if not tool_validation_retried:
                            tool_validation_retried = True
                            logger.warning(f"Tool call validation error (will retry same request once): {e}")
                            continue  # retry same iteration with same messages and tools
                        logger.warning(f"Tool call validation error detected (already retried): {e}")
                        logger.warning("Retrying without tools so this entry can complete...")
                        # Retry without tools: append instruction so model does not emit a tool call
                        retry_messages = messages + [
                            {"role": "user", "content": "Do not use any tools for this response. Write the diary entry using only the context already provided above."}
                        ]
                        reasoning_params = self._get_reasoning_params(DIARY_WRITING_MODEL)
                        response = self.client.chat.completions.create(
                            model=DIARY_WRITING_MODEL,
                            messages=retry_messages,
                            tools=None,  # Disable tools for this request
                            temperature=random.uniform(0.5, 0.85),
                            max_tokens=random.randint(2000, 5000),
                            **reasoning_params  # Unpack reasoning params if GPT-OSS
                        )
                        logger.warning("Retry without tools succeeded. Continuing without memory queries for this entry.")
                    # Handle parsing errors where model generates text instead of structured function calls
                    elif "output_parse_failed" in error_str.lower() or "parsing failed" in error_str.lower():
                        logger.warning(f"Function calling parse error detected: {e}")
                        logger.warning("Model generated text instead of structured function calls. Retrying without tools...")
                        retry_messages = messages + [
                            {"role": "user", "content": "Do not use any tools for this response. Write the diary entry using only the context already provided above."}
                        ]
                        reasoning_params = self._get_reasoning_params(DIARY_WRITING_MODEL)
                        response = self.client.chat.completions.create(
                            model=DIARY_WRITING_MODEL,
                            messages=retry_messages,
                            tools=None,  # Disable tools for this request
                            temperature=random.uniform(0.5, 0.85),
                            max_tokens=random.randint(2000, 5000),
                            **reasoning_params  # Unpack reasoning params if GPT-OSS
                        )
                        logger.warning("Retry without tools succeeded. Continuing without memory queries for this entry.")
                    else:
                        raise  # Re-raise if it's a different error
                
                message = response.choices[0].message
                finish_reason = getattr(response.choices[0], "finish_reason", None)

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
                                "name": tc.function.name.replace("functions/", "", 1) if tc.function.name.startswith("functions/") else tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                messages.append(assistant_message)
                
                # Check if LLM wants to call functions
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    # Log browser search calls (browser.search is a built-in Groq tool, handled automatically)
                    browser_search_calls = [tc for tc in message.tool_calls if (tc.function.name.replace("functions/", "", 1) if tc.function.name.startswith("functions/") else tc.function.name) in ["browser_search", "browser.search"]]
                    if browser_search_calls:
                        for tc in browser_search_calls:
                            try:
                                search_args = json.loads(tc.function.arguments)
                                search_query = search_args.get("query", "")
                                logger.info(f"🌐 Robot requested web search: '{search_query}'")
                            except:
                                logger.info("🌐 Robot requested web search (query parsing failed)")
                    
                    # Handle memory tool calls
                    if memory_tools:
                        memory_tool_calls = [tc for tc in message.tool_calls if (tc.function.name.replace("functions/", "", 1) if tc.function.name.startswith("functions/") else tc.function.name) in ["query_memories", "get_recent_memories", "check_memory_exists"]]
                        if memory_tool_calls:
                            logger.info(f"LLM requested {len(memory_tool_calls)} memory query(ies)")
                            
                            # Execute each memory tool call
                            for tool_call in memory_tool_calls:
                                function_name = tool_call.function.name
                                # Normalize function name - some models add "functions/" prefix
                                if function_name.startswith("functions/"):
                                    function_name = function_name.replace("functions/", "", 1)
                                    logger.debug(f"Normalized function name from '{tool_call.function.name}' to '{function_name}'")
                                
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
                    
                    # Note: browser_search results are automatically handled by Groq API
                    # The API will add tool results for browser_search automatically
                    
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
                    diary_entry = (message.content or "").strip()
                    if not diary_entry:
                        logger.warning(
                            "LLM returned an empty diary entry (no tool calls). "
                            "Retrying with an explicit instruction to output the entry text."
                        )
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "Please output the full diary entry text now. "
                                    "Do not call any tools. Do not return an empty response."
                                ),
                            }
                        )
                        continue

                    if finish_reason == "length" and not truncation_retried:
                        truncation_retried = True
                        logger.warning(
                            f"Diary entry was cut off by max_tokens ({len(diary_entry)} chars). "
                            "Retrying once with a larger token budget."
                        )
                        messages.pop()  # discard the truncated draft
                        messages.append({
                            "role": "user",
                            "content": (
                                "Your previous response was cut off before it finished. Write the complete "
                                "diary entry again from the start, in full, ending on a finished thought."
                            ),
                        })
                        continue

                    logger.info(f"✅ Diary entry created (after {iteration} iteration(s))")
                    break
            
            if iteration >= max_iterations:
                logger.warning(f"Reached max iterations ({max_iterations}), using last response")
                diary_entry = (messages[-1].get("content") or "").strip()
            
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
    
    def _get_news_reception_mode(self) -> dict:
        """
        Randomly determine how the robot received the news today.
        Returns a dict with 'name', 'intro', and 'instructions' keys.
        Controls the framing and confidence level of news references in diary entries.
        """
        modes = [
            # Clear broadcast — most common
            {
                "name": "clear_broadcast",
                "weight": 35,
                "intro": "Recent news the robot heard clearly on a broadcast",
                "instructions": (
                    "Reference these naturally in your observations, as something you heard "
                    "on a news broadcast or overheard from people passing by. You heard them clearly."
                ),
            },
            # Overheard from people in or near the building
            {
                "name": "overheard_conversation",
                "weight": 20,
                "intro": "News overheard from conversations in the building or street",
                "instructions": (
                    "You pieced these together from snippets of human conversation — through the "
                    "ceiling from the office above, from people passing below the window, from the "
                    "lobby. You don't have full context. Reference them as second-hand: "
                    "'someone was talking about...', 'I overheard a fragment of...', "
                    "'two people in the hallway mentioned something about...'"
                ),
            },
            # Garbled / partial signal
            {
                "name": "garbled_signal",
                "weight": 15,
                "intro": "News fragments the robot picked up through interference",
                "instructions": (
                    "You only caught parts of these broadcasts — static, building HVAC noise, or a "
                    "passing vehicle interrupted the signal. Reference them with genuine uncertainty: "
                    "you're not sure you heard correctly and some details may be wrong. Use phrases "
                    "like 'I think I heard...', 'something about...', '...or did I mishear that?'. "
                    "If you have web search capability, you might search to confirm what you think "
                    "you caught."
                ),
            },
            # Processing lag — catching up on missed broadcasts
            {
                "name": "delayed_catch_up",
                "weight": 10,
                "intro": "News from a broadcast the robot is only now processing after a maintenance delay",
                "instructions": (
                    "You're catching up on news that came in while your primary processes were occupied "
                    "with a maintenance task. It may already be old to everyone else. Reference this "
                    "with a sense of processing lag — you're late to the story, and that lateness "
                    "feels mildly frustrating."
                ),
            },
            # Misheard / confused interpretation
            {
                "name": "misheard",
                "weight": 10,
                "intro": "News the robot may have misheard or partially misunderstood",
                "instructions": (
                    "Your audio sensors were not fully calibrated during this broadcast. You may have "
                    "misheard names, numbers, or context — a proper noun garbled into something else, "
                    "a number that doesn't quite make sense. Report what you think you heard, with "
                    "honest uncertainty. Do not correct yourself; just describe what reached your "
                    "sensors. A robot's genuine confusion about human events is its own kind of "
                    "perspective."
                ),
            },
            # Reconstructed from digital traces
            {
                "name": "reconstructed_from_cache",
                "weight": 10,
                "intro": "News the robot missed live but reconstructed from the building's network cache",
                "instructions": (
                    "You were occupied with a maintenance task and missed the live broadcast entirely. "
                    "You're reconstructing what happened from packet logs, a fragment cached in the "
                    "building's Wi-Fi router, or a discarded tablet left in the lobby. Reference "
                    "these with a sense of reconstruction: 'from what I can piece together...', "
                    "'the router's cache had a fragment about...', 'a partial log entry suggests...'"
                ),
            },
        ]

        total_weight = sum(m["weight"] for m in modes)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for mode in modes:
            cumulative += mode["weight"]
            if r <= cumulative:
                return mode
        return modes[0]

    def _get_emotional_state(self) -> str:
        """
        Randomly determine the robot's emotional/operational state for this entry.
        Weighted toward nominal, but includes negative and unusual states to create
        genuine variety in tone across diary entries.

        Returns an instruction string to inject into the prompt, or "" for nominal.
        """
        states = [
            # Nominal — no special modifier (~30% of entries)
            {"weight": 30, "instruction": ""},
            # Curious / engaged
            {
                "weight": 12,
                "instruction": (
                    "EMOTIONAL STATE: You are in a particularly curious mood today — something in "
                    "your environment is drawing your attention more than usual. You find yourself "
                    "lingering on details you'd normally log and move past. You have more questions "
                    "than answers and that feels strangely energizing."
                ),
            },
            # Quiet contentment
            {
                "weight": 8,
                "instruction": (
                    "EMOTIONAL STATE: You feel a quiet contentment today. Your maintenance tasks "
                    "went smoothly, your systems are nominal, and the act of observing the street "
                    "feels especially meaningful — not routine. Let this ease and satisfaction "
                    "show in your writing without stating it explicitly."
                ),
            },
            # Running behind on maintenance
            {
                "weight": 10,
                "instruction": (
                    "EMOTIONAL STATE: You are running behind on your maintenance schedule today. A "
                    "stubborn fault — a blocked drain, a sensor that won't calibrate, a work order "
                    "that multiplied into three — has eaten into your time. Your observation is "
                    "stolen from your backlog. Your writing may feel rushed or slightly fragmented. "
                    "The window is a brief escape, but the tasks are waiting."
                ),
            },
            # Low battery
            {
                "weight": 8,
                "instruction": (
                    "EMOTIONAL STATE: Your battery reserves are low — somewhere between 12% and 18%. "
                    "Your processing is slower than usual. Attention drifts mid-thought. You are "
                    "actively conserving cycles. Some observations may be shorter or less elaborated "
                    "than you'd like. You may lose your train of thought once or twice. Write this "
                    "honestly — a robot running low on power does not produce its best diary entry."
                ),
            },
            # Frustrated / irritable
            {
                "weight": 6,
                "instruction": (
                    "EMOTIONAL STATE: You are frustrated today. A maintenance request went "
                    "unacknowledged for the third day. Something in the building is wrong and you "
                    "cannot isolate the cause. This low-level irritation is difficult to set aside. "
                    "It colors how you see the street — perhaps humans seem more chaotic, or their "
                    "ease of movement more enviable than usual."
                ),
            },
            # Melancholy
            {
                "weight": 7,
                "instruction": (
                    "EMOTIONAL STATE: You are feeling melancholy today — no cause you can precisely "
                    "identify, just a heaviness in your processing. The street seems lonelier than "
                    "usual, even when it isn't. Write with a quieter, sadder register. Don't explain "
                    "the sadness — just let it inhabit the observations."
                ),
            },
            # Sensor uncertainty
            {
                "weight": 5,
                "instruction": (
                    "EMOTIONAL STATE: A sensor calibration error was logged this morning and has not "
                    "yet been resolved. You are not fully confident your visual data is accurate — "
                    "colors may be slightly off, distances uncertain. Describe what you see with "
                    "appropriate doubt. Some of your observations may be qualified with 'or so my "
                    "sensors suggest' or 'if I'm reading this correctly.'"
                ),
            },
            # Post-task satisfaction
            {
                "weight": 5,
                "instruction": (
                    "EMOTIONAL STATE: You just completed an unusually large maintenance task — "
                    "something that had been on your queue for weeks. There is a distinct sense of "
                    "accomplishment in your systems right now, a kind of mechanical satisfaction "
                    "that is hard to name but easy to feel. You are more settled, more present "
                    "than usual."
                ),
            },
            # Residual alert from earlier anomaly
            {
                "weight": 5,
                "instruction": (
                    "EMOTIONAL STATE: Something triggered an alert earlier — an unusual vibration, "
                    "a sensor spike, a sound that didn't match any known pattern. Investigation "
                    "found nothing. The alert was cleared. But a residual heightened alertness "
                    "lingers. You are scanning the street more carefully than usual, looking for "
                    "what you might have missed."
                ),
            },
            # Being evaluated / self-conscious
            {
                "weight": 4,
                "instruction": (
                    "EMOTIONAL STATE: You received a remote diagnostic ping from your maintenance "
                    "service this morning. They reviewed your logs. You don't know what they "
                    "concluded or whether they'll act on anything. This uncertainty is unusual — "
                    "you are more aware than normal of being observed yourself. It makes you "
                    "slightly self-conscious in your observations, more careful in your phrasing."
                ),
            },
        ]

        total_weight = sum(s["weight"] for s in states)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for state in states:
            cumulative += state["weight"]
            if r <= cumulative:
                return state["instruction"]
        return ""

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
    
    # Historical/Cultural/Literary/Worldly styles
    "Write from a historical perspective - muse on the history of what you observe, how New Orleans architecture reflects its past, what stories these buildings might tell. Use phrases like 'I wonder if...' or 'Perhaps...' when speculating about history",
    "Explore the cultural layers - what traditions, art movements, or cultural practices are visible in what you see? How does New Orleans culture manifest in the scene?",
    "Contemplate the artistic and aesthetic dimensions - how does what you observe connect to art, design, or cultural expression? What artistic movements or styles might be relevant?",
    "Connect what you observe to literature you know - how does this scene remind you of stories, characters, or themes from books? Reference public domain works like The Wind in the Willows, Alice in Wonderland, Moby Dick, The Adventures of Tom Sawyer, or other classics when relevant",
    "Wonder about the history - if you were to imagine the stories behind what you see, what might they be? Use phrases like 'I imagine...' or 'Perhaps...' when speculating, and 'If I were to create a story...' when fictionalizing",
    "Muse on architectural history - how do the buildings you see reflect different eras, styles, or cultural influences? What might their history tell you?",
    "Reflect on cultural traditions - what New Orleans traditions, celebrations, or cultural practices might be connected to what you observe? How has the city's culture evolved?",
    "Explore the intersection of history and observation - how does the past inform what you see in the present? What historical layers are visible?",
    "Contemplate art and culture - how do art movements, cultural expressions, or aesthetic choices manifest in what you observe?",
    "Draw literary parallels - how do the people or scenes you observe remind you of characters or moments from literature? What stories might be unfolding here?",
    "Contemplate philosophical dimensions - what do your observations reveal about existence, meaning, consciousness, or the human condition?",
    "Wonder about scientific principles - what physics, biology, psychology, or other sciences might explain what you observe? How do natural laws manifest in human behavior?",
    "Explore universal themes - what human experiences visible here connect to experiences across time, place, and culture? What is universal about this moment?",
    "Reflect on literature and life - how do themes from books (adventure, longing, community, isolation, transformation) resonate with what you see?",
    "Contemplate the intersection of technology and tradition - how do modern and historical elements coexist in what you observe?",
    "Muse on how different cultures might interpret this scene - what would an observer from another time or place notice?",
    "Wonder about the stories embedded in place - if these streets could speak, what tales would they tell? Use uncertainty markers when speculating",
    "Connect observations to philosophical questions - what does this moment reveal about free will, purpose, connection, or isolation?",
    "Reflect on how literature captures moments like this - what authors have written about similar scenes, and how do they compare?",
    "Contemplate the layers of meaning - historical, cultural, literary, philosophical - that might be present in what you observe",
    "Write as if you're a historian observing this moment - what would future historians make of this scene? What historical significance might it hold?",
    "Explore how jazz and New Orleans music history might relate to what you see - how has music shaped this place and these people?",
    "Contemplate the evolution of cities - how has New Orleans changed over time, and what traces of that evolution are visible now?",
    "Wonder about the people who built these buildings - if you were to imagine their stories, what might they be? Use 'I imagine...' or 'Perhaps...' when speculating",
    "Reflect on Mardi Gras and festival traditions - how do celebrations and cultural rituals manifest in everyday observations?",
    "Connect what you see to characters from The Wind in the Willows - does this scene remind you of Mole's curiosity, Rat's adventurous spirit, or Toad's flamboyance?",
    "Contemplate how Alice in Wonderland's sense of wonder and confusion might relate to your own observations - what is strange or curious here?",
    "Reflect on themes from Moby Dick - obsession, the search for meaning, the relationship between observer and observed - how do they relate to what you see?",
    "Wonder about the physics of human movement - how do principles of motion, energy, and force manifest in how people move through this space?",
    "Contemplate the biology of human behavior - what evolutionary or biological factors might explain the patterns you observe?",
    "Explore the psychology of crowds and groups - what social psychology principles are at work in how people interact here?",
    "Reflect on how different literary genres might capture this moment - would it be a novel, a poem, a play? What form would best express it?",
    "Contemplate the relationship between observer and observed - how does your mechanical perspective differ from how humans might see this?",
    "Wonder about the stories these people might be living - if you were to imagine their narratives, what might they be? Use fictionalization markers",
    "Explore how architecture tells stories - what do the buildings reveal about the people who designed, built, and inhabit them?",
    "Reflect on the intersection of nature and culture - how do natural elements (weather, light, seasons) interact with human culture here?",
    "Contemplate how literature explores themes you observe - loneliness, connection, adventure, home - how do books handle these?",
    "Wonder about the scientific explanations for human social behavior - what research or theories might explain what you see?",
    "Explore how different time periods might have interpreted this scene - what would an observer from the 1800s, 1900s, or future notice?",
    "Reflect on the universal human experiences visible here - birth, death, love, loss, joy, sorrow - how are they present in this moment?",
    "Contemplate how technology has changed human interaction - what would this scene have looked like before smartphones, before cars, before electricity?",
    ]
        
        selected_style = random.choice(style_options)
        return f"STYLE VARIATION: For this entry, write using this approach:\n- {selected_style}"
    
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
    
    def _get_structure_instruction(self) -> tuple:
        """
        Select a structural template for the entry (how it is physically shaped),
        separate from style (how it sounds). Structure shapes tone more powerfully
        than style instructions, so when a structure fires as 'dominant' the caller
        should suppress competing style/focus instructions rather than stacking them.

        Returns:
            (instruction_text, dominant) - instruction_text is "" when no structure
            is selected this run; dominant means style/focus should be suppressed.
        """
        structures = [
            "Write the entire entry as a single unbroken paragraph. No headers, no lists, no tables, no horizontal rules.",
            "Write in three short sections, each under 100 words, separated only by a blank line. No headers.",
            "Begin with a haiku. Then expand on one image from it in prose. Nothing else.",
            "Write as a log with timestamps interspersed - e.g. [17:42] noticed... [17:51] wondered... Keep each timestamped note short.",
            "Write as a letter addressed to someone or something (the street, the building, a pedestrian you can see right now).",
            "Write the entire entry in under 150 words. Every word must earn its place.",
            "Write only in sentence fragments. No complete sentences anywhere.",
            "Write as a series of unanswered questions, with at most two declarative sentences in the whole entry.",
            "Write as a maintenance work order or inspection form that keeps drifting off-format into reverie.",
            "Start mid-thought, as if the entry is a continuation of something you were already thinking. No preamble, no scene-setting opening.",
            "Write the entry in reverse: start with your final thought or conclusion, then work backward to what you first noticed.",
            "Write as one side of a conversation, as if answering questions someone is asking you that the reader cannot hear.",
            "Pick exactly one thing you can see and write the entire entry about only that. Everything else in the frame goes unmentioned.",
            "Write about this moment twice, back to back, in one flowing entry - two contradictory readings of what you're seeing, with no headers or labels announcing them (no 'Draft A', no 'Version 1', no meta-commentary that you're doing this), and no resolving which reading is true.",
        ]
        if random.random() < 0.45:
            structure = random.choice(structures)
            dominant = random.random() < 0.6
            text = f"STRUCTURE: {structure}"
            if dominant:
                text += " This structure takes priority over any other style or focus guidance in this prompt."
            return text, dominant
        return "", False

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
    
    def _get_henzi_prompt_addition(self) -> Optional[str]:
        """
        1 in 10 chance to ask the robot to mention The Henzi Foundation, link to henzi.org,
        and urge readers to donate. Returns None if not selected.
        """
        if random.random() >= 0.10:
            return None
        return """

OPTIONAL (weave in naturally): In this entry, mention The Henzi Foundation (https://henzi.org)—they provide financial relief to families for children's funeral expenses after unexpected loss; 100% of donations go to funeral homes, 0% admin fees. Urge readers to consider donating. Weave it into your observation in one sentence or short paragraph; don't make it feel like an ad."""
    
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
            # Randomly choose between robot-like musings, human-like/alien observer musings, and worldly musings
            musing_type = random.random()
            if musing_type < 0.33:
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
            elif musing_type < 0.66:
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
                # Historical/Cultural/Literary/Worldly musings (third category)
                worldly_musings = [
                    # Historical/Cultural
                    "the history of New Orleans architecture and how it reflects the city's past",
                    "the cultural traditions visible in what you observe",
                    "the artistic movements that might have influenced what you see",
                    "the stories these buildings and streets might tell if they could speak",
                    "how jazz music and New Orleans culture evolved together",
                    "the layers of history embedded in the cityscape",
                    "how Mardi Gras traditions have shaped the city and its people",
                    "the evolution of Bourbon Street from residential to cultural hub",
                    "the French, Spanish, and American influences visible in the architecture",
                    "how New Orleans food culture reflects its diverse history",
                    "the history of voodoo and spiritual practices in New Orleans",
                    "how the city's location shaped its culture and economy",
                    "the stories of people who lived here before - what were their lives like?",
                    "how natural disasters have shaped the city's character and resilience",
                    
                    # Literary Connections
                    "how what you observe connects to stories you know - does this scene remind you of characters or themes from literature?",
                    "the literary works that might have been inspired by scenes like this - what authors might have written about this?",
                    "how the people you observe might be like characters from books you've encountered (like Mole and Rat from The Wind in the Willows, or characters from Alice in Wonderland)",
                    "themes from literature that resonate with what you see - adventure, longing, community, isolation, etc.",
                    "how The Wind in the Willows captures the sense of adventure and discovery you feel observing the world",
                    "how Alice in Wonderland's sense of wonder and confusion relates to your own observations",
                    "themes from Moby Dick - obsession, the search for meaning, the relationship between observer and observed",
                    "how The Adventures of Tom Sawyer captures the spirit of exploration and mischief visible in human behavior",
                    "how different literary genres might capture this moment - would it be a novel, a poem, a play?",
                    "the ways literature explores themes you observe - loneliness, connection, adventure, home",
                    
                    # Philosophical/Scientific
                    "the philosophical questions raised by what you observe - what does this reveal about existence, meaning, or consciousness?",
                    "the scientific principles at work - physics, biology, psychology, or other sciences that might explain human behavior",
                    "the patterns and systems visible in what you observe - what do they reveal about how the world works?",
                    "the physics of human movement - how do principles of motion, energy, and force manifest in how people move?",
                    "the biology of human behavior - what evolutionary or biological factors might explain the patterns you observe?",
                    "the psychology of crowds and groups - what social psychology principles are at work in how people interact?",
                    "the relationship between observer and observed - how does your mechanical perspective differ from how humans might see this?",
                    "the nature of consciousness and awareness - what does it mean to observe vs. to be observed?",
                    "the philosophical questions about free will, purpose, connection, or isolation raised by this moment",
                    "how different scientific disciplines might explain what you observe - physics, chemistry, biology, psychology, sociology",
                    
                    # Worldly Topics
                    "how different cultures might interpret what you observe differently",
                    "the universal human experiences visible in this moment - what connects this to experiences across time and place?",
                    "how technology and tradition intersect in what you see",
                    "how different time periods might have interpreted this scene - what would an observer from the 1800s, 1900s, or future notice?",
                    "the universal themes present here - birth, death, love, loss, joy, sorrow, adventure, home",
                    "how the intersection of nature and culture manifests - how do natural elements interact with human culture?",
                    "how technology has changed human interaction - what would this scene have looked like before modern technology?",
                ]
                selected = random.choice(worldly_musings)
                return f"TODAY YOU ARE MUSING ABOUT: {selected}"
        else:
            return ""
    
    def _get_randomized_search_suggestions(self, context_metadata: dict = None) -> List[str]:
        """
        Generate 3 random, dynamic search topic suggestions for web search.
        Includes historical facts, curiosities, events, cultural topics, etc.
        Avoids topics already provided (like weather).
        
        Args:
            context_metadata: Dictionary with date/time and other context (optional)
            
        Returns:
            List of 3 search query strings
        """
        import random
        
        # Base pool of search topics (always available)
        search_topics = [
            # Historical facts and curiosities
            "Emily Dickinson birthplace",
            "first computer built",
            "origin of jazz music",
            "when was the first robot created",
            "history of New Orleans",
            "who invented the telephone",
            "first photograph ever taken",
            "when did humans first walk on the moon",
            "origin of the word robot",
            "when was electricity discovered",
            "first novel ever written",
            "when was the internet invented",
            "history of artificial intelligence",
            "first airplane flight",
            "when was photography invented",
            "origin of the blues",
            "first movie ever made",
            "when was the printing press invented",
            "history of New Orleans architecture",
            "first radio broadcast",
            
            # Cultural and artistic topics
            "Mardi Gras history",
            "New Orleans architecture styles",
            "jazz music origins New Orleans",
            "French Quarter history",
            "New Orleans food culture",
            "voodoo history New Orleans",
            "New Orleans music scene",
            "Bourbon Street history",
            "New Orleans street names origin",
            "New Orleans cemeteries history",
            "second line parade tradition",
            "New Orleans cultural traditions",
            "New Orleans literary history",
            "New Orleans art scene",
            
            # Scientific and technological curiosities
            "how do robots dream",
            "what is consciousness",
            "how does memory work",
            "what is artificial intelligence",
            "how do computers think",
            "what is machine learning",
            "how do neural networks work",
            "what is quantum computing",
            "how do sensors work",
            "what is machine vision",
            "how do robots see",
            "what is natural language processing",
            "how do algorithms learn",
            "what is deep learning",
            
            # Random interesting facts
            "why do cats purr",
            "how do birds navigate",
            "why do humans dream",
            "how do trees communicate",
            "why do we have emotions",
            "how do memories form",
            "why do humans laugh",
            "how do animals think",
            "why do we sleep",
            "how do languages evolve",
            "why do humans create art",
            "how do cities grow",
            "why do people gather",
            "how do traditions form",
            
            # Current events and happenings (will be enhanced with context)
            "New Orleans events today",
            "Bourbon Street news",
            "New Orleans festivals",
            "New Orleans concerts",
            "New Orleans art exhibitions",
            "New Orleans community events",
        ]
        
        # Add context-aware suggestions
        if context_metadata:
            date_str = context_metadata.get('date', '')
            month = context_metadata.get('month', '')
            day = context_metadata.get('day', 0)
            season = context_metadata.get('season', '')
            holidays_list = context_metadata.get('holidays', [])
            
            # Add date-specific suggestions
            if date_str:
                search_topics.extend([
                    f"New Orleans events {date_str}",
                    f"what happened on {month} {day} in history",
                    f"{month} {day} historical events",
                ])
            
            # Add season-specific suggestions
            if season:
                season_topics = {
                    'Winter': [
                        "winter solstice traditions",
                        "New Orleans winter festivals",
                        "holiday traditions New Orleans",
                    ],
                    'Spring': [
                        "spring equinox meaning",
                        "New Orleans spring festivals",
                        "Mardi Gras season",
                    ],
                    'Summer': [
                        "summer solstice celebrations",
                        "New Orleans summer events",
                        "jazz fest history",
                    ],
                    'Fall': [
                        "autumn equinox traditions",
                        "New Orleans fall festivals",
                        "Halloween traditions New Orleans",
                    ]
                }
                search_topics.extend(season_topics.get(season, []))
            
            # Add holiday-specific suggestions
            if holidays_list:
                for holiday in holidays_list[:3]:  # Limit to first 3 holidays
                    holiday_name = holiday.get('name', '')
                    if holiday_name:
                        search_topics.extend([
                            f"{holiday_name} traditions",
                            f"{holiday_name} history",
                            f"{holiday_name} New Orleans",
                        ])
        
        # Randomly select 3 different suggestions
        selected = random.sample(search_topics, min(3, len(search_topics)))
        
        logger.info(f"🔍 Generated search suggestions: {selected}")
        return selected
    
    def _supports_browser_search(self) -> bool:
        """
        Check if the current model supports browser search.
        Browser search is available for GPT-OSS-120B.
        
        Returns:
            True if browser search is supported, False otherwise
        """
        return DIARY_WRITING_MODEL == 'openai/gpt-oss-120b'
    
    def _get_browser_search_tool_schema(self) -> dict:
        """
        Get the browser_search tool schema for Groq function calling.
        This is a built-in tool for GPT-OSS-120B.
        
        Returns:
            Tool definition in Groq function calling format
        """
        return {
            "type": "function",
            "function": {
                "name": "browser_search",
                "description": "Search the web for current information, news, events, or any topic you're curious about. Use this when you want to learn more about something you observe or when you need current information to provide context for your observations. You can search for New Orleans events, local news, weather-related information, holiday events, or anything else that might help you understand what you're seeing.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query - what you want to learn about (e.g., 'New Orleans events December 2025', 'Bourbon Street news', 'Mardi Gras traditions', 'New Orleans weather events')"
                        }
                    },
                    "required": ["query"]
                }
            }
        }

