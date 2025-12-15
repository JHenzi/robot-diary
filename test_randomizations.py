#!/usr/bin/env python3
"""Test script to output randomized prompt elements."""

import sys
from pathlib import Path
from datetime import datetime
import pytz

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.llm.client import GroqClient
from src.config import LOCATION_TIMEZONE

def test_randomizations(num_runs=5):
    """Test and display randomized prompt elements."""
    
    client = GroqClient()
    
    # Create mock context metadata
    location_tz = pytz.timezone(LOCATION_TIMEZONE)
    now = datetime.now(location_tz)
    
    context_metadata = {
        'date': now.strftime('%B %d, %Y'),
        'day_of_week': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()],
        'time': now.strftime('%I:%M %p'),
        'timezone': 'CST' if now.astimezone(location_tz).dst() == pytz.timezone('UTC').localize(datetime(2024, 1, 1)).dst() else 'CDT',
        'season': 'Winter',  # Mock season
        'time_of_day': 'evening',
        'observation_type': 'evening',
    }
    
    # Mock recent memory (empty for testing)
    recent_memory = []
    
    print("=" * 80)
    print("RANDOMIZATION TEST - Running {} iterations".format(num_runs))
    print("=" * 80)
    print()
    
    for i in range(num_runs):
        print(f"\n{'='*80}")
        print(f"ITERATION {i+1}")
        print(f"{'='*80}\n")
        
        # Test reflection instructions (musing events)
        print("💭 REFLECTION INSTRUCTIONS (Musing Events):")
        reflection = client._get_reflection_instructions()
        if reflection:
            print(f"   {reflection}")
        else:
            print("   (No reflection instruction - 50% chance)")
        print()
        
        # Test style variations
        print("🎨 STYLE VARIATIONS:")
        style = client._get_style_variation()
        print(f"   {style}")
        print()
        
        # Test perspective shift
        print("👁️  PERSPECTIVE SHIFT:")
        perspective = client._get_perspective_shift()
        print(f"   {perspective}")
        print()
        
        # Test focus instruction
        print("🎯 FOCUS INSTRUCTION:")
        focus = client._get_focus_instruction(context_metadata)
        print(f"   {focus}")
        print()
        
        # Test creative challenge
        print("✨ CREATIVE CHALLENGE:")
        challenge = client._get_creative_challenge()
        if challenge:
            print(f"   {challenge}")
        else:
            print("   (No creative challenge - 40% chance)")
        print()
        
        # Test personality note
        print("🤖 PERSONALITY NOTE:")
        personality = client._get_personality_note(memory_count=10, context_metadata=context_metadata)
        print(f"   {personality}")
        print()
        
        # Test seasonal note
        print("🍂 SEASONAL NOTE:")
        seasonal = client._get_seasonal_note(context_metadata)
        if seasonal:
            print(f"   {seasonal}")
        else:
            print("   (No seasonal note)")
        print()
        
        # Test randomized identity (just show it was selected, not full content)
        print("📚 RANDOMIZED IDENTITY:")
        identity = client._build_randomized_identity()
        # Count backstory points
        backstory_count = identity.count('-')
        print(f"   (Identity built with {backstory_count} backstory points)")
        print()
        
        if i < num_runs - 1:
            print("-" * 80)
            print()

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    
    # Show statistics for musing events
    print("\n📊 MUSING EVENT STATISTICS:")
    print("   Running additional test to show distribution...")
    
    robot_count = 0
    human_count = 0
    none_count = 0
    
    for _ in range(100):
        reflection = client._get_reflection_instructions()
        if not reflection:
            none_count += 1
        elif 'writing pseudo-code' in reflection or 'debugging' in reflection or 'optimizing' in reflection or 'running diagnostics' in reflection:
            robot_count += 1
        else:
            human_count += 1
    
    print(f"   Robot-like musings: {robot_count}%")
    print(f"   Human-like musings: {human_count}%")
    print(f"   No musing event: {none_count}%")
    
    # Show statistics for style types
    print("\n📊 STYLE TYPE STATISTICS:")
    print("   Running additional test to show style distribution...")
    
    style_categories = {
        'Detail-focused': ['Focus on specific details', 'Focus on sensory details', 'Focus on micro-moments'],
        'Tone-based': ['philosophical tone', 'more poetically', 'more humorously', 'more melancholically', 'more whimsically'],
        'Structural': ['narrative style', 'more conversationally', 'stream of consciousness', 'in fragments'],
        'Analytical': ['analytical perspective', 'patterns and repetition', 'Focus on contrasts'],
        'Speculative': ['more speculatively', 'as an anthropologist', 'as a time traveler'],
        'Emotional/Spiritual': ['emotional depth', 'more spiritually', 'with wonder'],
        'Perspective shifts': ["bird's eye view", 'ground level', "you're invisible"],
        'Temporal': ['with urgency', 'with nostalgia', 'with anticipation'],
        'Robot-specific': ['minor malfunction', 'robot speak', 'energy sources', 'battery is low', 'overheating', 
                          'maintenance mode', 'firmware updates', 'memory is fragmented', 'power-saving mode',
                          'sensor drift', 'backup power', 'processing in binary', 'calculating probabilities',
                          'debug mode', 'translating human behavior into machine code', 'memory leak',
                          'running low on storage', 'safe mode', 'network latency', 'running diagnostics on yourself'],
        'Personable robot': ['mechanical curiosity but emotional warmth', 'Think systematically but feel personally',
                            'Observe like a machine, reflect like a person', 'robotic precision but human wonder',
                            'mechanical lens to see uniquely']
    }
    
    style_counts = {category: 0 for category in style_categories.keys()}
    style_counts['Unknown'] = 0
    
    for _ in range(200):  # Test 200 style selections (100 pairs)
        style = client._get_style_variation()
        # Extract the style lines (skip the header)
        style_lines = [line.strip('- ').strip() for line in style.split('\n')[1:] if line.strip()]
        
        for style_line in style_lines:
            categorized = False
            for category, keywords in style_categories.items():
                if any(keyword.lower() in style_line.lower() for keyword in keywords):
                    style_counts[category] += 1
                    categorized = True
                    break
            if not categorized:
                style_counts['Unknown'] += 1
    
    total_styles = sum(style_counts.values())
    print(f"   Total style selections tested: {total_styles}")
    print()
    print("   Style category distribution:")
    for category, count in sorted(style_counts.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            percentage = (count / total_styles) * 100
            print(f"      {category:25s}: {count:3d} ({percentage:5.1f}%)")
    print()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Test randomized prompt elements')
    parser.add_argument('-n', '--num-runs', type=int, default=5, 
                       help='Number of test iterations (default: 5)')
    args = parser.parse_args()
    
    test_randomizations(args.num_runs)
