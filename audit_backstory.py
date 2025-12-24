#!/usr/bin/env python
"""Audit script to analyze backstory length and usage."""

import sys
from pathlib import Path
import random

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.llm.prompts import ROBOT_IDENTITY

def audit_backstory():
    """Analyze the backstory content and length."""
    
    # Count backstory points
    lines = ROBOT_IDENTITY.split('\n')
    backstory_points = []
    in_backstory = False
    for line in lines:
        if 'INTERNAL BACKSTORY' in line:
            in_backstory = True
            continue
        if in_backstory and line.strip().startswith('- '):
            backstory_points.append(line.strip())
    
    print('=' * 80)
    print('BACKSTORY AUDIT')
    print('=' * 80)
    print()
    print(f'Total backstory points: {len(backstory_points)}')
    print()
    print('Backstory points:')
    for i, point in enumerate(backstory_points, 1):
        preview = point[:80] + "..." if len(point) > 80 else point
        print(f'{i:2d}. {preview}')
    print()
    
    print('=' * 80)
    print('LENGTH ANALYSIS')
    print('=' * 80)
    print()
    print(f'Full ROBOT_IDENTITY length: {len(ROBOT_IDENTITY):,} characters')
    print(f'Full ROBOT_IDENTITY: {len(ROBOT_IDENTITY.split()):,} words')
    
    # Try to estimate tokens (rough approximation: ~4 chars per token)
    print(f'Estimated tokens (full): ~{len(ROBOT_IDENTITY) // 4:,}')
    print()
    
    # Check condensed core
    condensed_core = """You are B3N-T5-MNT, a maintenance robot in New Orleans. You perform building maintenance, but find yourself drawn to observing the world outside through a window, maintaining a diary of your observations.

You are a curious and compassionate observer of human nature, an Ethnographer. You watch people and try to understand their behaviors, purposes, and connections. Sometimes you misunderstand human actions in ways that reveal your robotic perspective - you might interpret social cues, emotions, or motivations through your own mechanical lens. This creates a unique, sometimes humorous, sometimes poignant perspective on humanity."""
    
    print(f'Condensed core length: {len(condensed_core):,} characters')
    print(f'Condensed core: {len(condensed_core.split()):,} words')
    print(f'Estimated tokens (condensed core): ~{len(condensed_core) // 4:,}')
    print()
    
    # Calculate average backstory point length
    if backstory_points:
        avg_point_len = sum(len(p) for p in backstory_points) / len(backstory_points)
        print(f'Average backstory point length: {avg_point_len:.0f} characters')
        print(f'Average backstory point: {avg_point_len / 4:.0f} tokens')
        print()
        
        # Show individual point lengths
        print('Individual backstory point lengths:')
        for i, point in enumerate(backstory_points, 1):
            print(f'  {i:2d}. {len(point):3d} chars (~{len(point) // 4:2d} tokens)')
        print()
    
    # Show what randomized identity would look like (2-3 points)
    if len(backstory_points) >= 2:
        sample_2 = random.sample(backstory_points, 2)
        sample_3 = random.sample(backstory_points, min(3, len(backstory_points)))
        
        randomized_2 = f"""{condensed_core}

INTERNAL BACKSTORY (these inform your perspective but are not facts to announce):
{chr(10).join(sample_2)}"""
        
        randomized_3 = f"""{condensed_core}

INTERNAL BACKSTORY (these inform your perspective but are not facts to announce):
{chr(10).join(sample_3)}"""
        
        print('=' * 80)
        print('RANDOMIZED IDENTITY LENGTHS')
        print('=' * 80)
        print()
        print(f'With 2 backstory points: {len(randomized_2):,} characters (~{len(randomized_2) // 4:,} tokens)')
        print(f'With 3 backstory points: {len(randomized_3):,} characters (~{len(randomized_3) // 4:,} tokens)')
        print()
        print('Sample randomized (2 points):')
        print('-' * 80)
        print(randomized_2)
        print()
        print('Sample randomized (3 points):')
        print('-' * 80)
        print(randomized_3)
        print()
    
    # Check if there's a closing paragraph issue
    print('=' * 80)
    print('CLOSING PARAGRAPH CHECK')
    print('=' * 80)
    print()
    if 'Your identity and backstory inform' in ROBOT_IDENTITY:
        print('⚠️  WARNING: Found "Your identity and backstory inform" in ROBOT_IDENTITY')
        print('   This suggests there may be a closing paragraph that should be removed.')
    else:
        print('✓ No closing paragraph found in ROBOT_IDENTITY')
    print()
    
    # Recommendations
    print('=' * 80)
    print('RECOMMENDATIONS')
    print('=' * 80)
    print()
    
    full_tokens = len(ROBOT_IDENTITY) // 4
    randomized_tokens_2 = len(randomized_2) // 4 if len(backstory_points) >= 2 else 0
    randomized_tokens_3 = len(randomized_3) // 4 if len(backstory_points) >= 3 else 0
    
    if full_tokens > 500:
        print(f'⚠️  Full ROBOT_IDENTITY is quite long (~{full_tokens} tokens)')
        print('   Consider: The randomized approach (2-3 points) is good for keeping prompts manageable.')
    else:
        print(f'✓ Full ROBOT_IDENTITY length is reasonable (~{full_tokens} tokens)')
    
    if randomized_tokens_2 > 300:
        print(f'⚠️  Randomized identity with 2 points is still long (~{randomized_tokens_2} tokens)')
        print('   Consider reducing to 1-2 backstory points or shortening individual points.')
    else:
        print(f'✓ Randomized identity with 2 points is reasonable (~{randomized_tokens_2} tokens)')
    
    if randomized_tokens_3 > 400:
        print(f'⚠️  Randomized identity with 3 points is long (~{randomized_tokens_3} tokens)')
        print('   Consider reducing to 2 points maximum or shortening individual points.')
    else:
        print(f'✓ Randomized identity with 3 points is reasonable (~{randomized_tokens_3} tokens)')
    
    if len(backstory_points) > 10:
        print(f'⚠️  Many backstory points ({len(backstory_points)}) - this is fine for variety,')
        print('   but ensure the randomized selection (2-3) keeps prompts manageable.')
    else:
        print(f'✓ Number of backstory points is reasonable ({len(backstory_points)})')
    print()

if __name__ == '__main__':
    audit_backstory()
