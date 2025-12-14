#!/usr/bin/env python
"""Debug script for holiday detection and formatting."""
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Enable debug logging to see what's happening
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s: %(message)s'
)

import pytz
from datetime import datetime, timedelta
from src.context.metadata import (
    get_holidays,
    get_upcoming_holidays,
    format_context_for_prompt,
    get_context_metadata,
    LOCATION_TZ,
    HOLIDAYS_AVAILABLE
)

# Check if holidays library is available
try:
    import holidays
    HOLIDAYS_LIB_AVAILABLE = True
    HOLIDAYS_VERSION = getattr(holidays, '__version__', 'unknown')
except ImportError:
    HOLIDAYS_LIB_AVAILABLE = False
    HOLIDAYS_VERSION = None

def test_holiday_detection():
    """Test holiday detection functions."""
    print("=" * 80)
    print("HOLIDAY DETECTION DEBUG")
    print("=" * 80)
    
    # Check library availability
    print("\n" + "-" * 80)
    print("LIBRARY STATUS:")
    print("-" * 80)
    print(f"  holidays library installed: {'✅ YES' if HOLIDAYS_LIB_AVAILABLE else '❌ NO'}")
    if HOLIDAYS_LIB_AVAILABLE:
        print(f"  Version: {HOLIDAYS_VERSION}")
    else:
        print("  ⚠️  Install with: pip install holidays")
        print("  ⚠️  Or run in Docker where it should be installed")
    print(f"  Module reports available: {'✅ YES' if HOLIDAYS_AVAILABLE else '❌ NO'}")
    
    # Test with current date
    now = datetime.now(LOCATION_TZ)
    print(f"\n📅 Current Date: {now.strftime('%B %d, %Y at %I:%M %p %Z')}")
    print(f"   Date only: {now.date()}")
    
    # Test today's holidays
    print("\n" + "-" * 80)
    print("TODAY'S HOLIDAYS:")
    print("-" * 80)
    today_holidays = get_holidays(now)
    if today_holidays:
        for holiday in today_holidays:
            print(f"  ✅ {holiday}")
    else:
        print("  ❌ No holidays today")
    
    # Test upcoming holidays
    print("\n" + "-" * 80)
    print("UPCOMING HOLIDAYS (next 30 days):")
    print("-" * 80)
    
    # Debug: manually trace through the function logic
    print("\n  🔍 Tracing function logic...")
    try:
        import holidays
        us_holidays = holidays.UnitedStates(years=[now.year, now.year + 1])
        la_holidays = holidays.US(state='LA', years=[now.year, now.year + 1])
        all_holidays = {}
        all_holidays.update(us_holidays)
        all_holidays.update(la_holidays)
        
        date_only = now.date()
        print(f"     Starting date: {date_only}")
        print(f"     Checking days 1-30...")
        
        # Debug: check what type of keys are in the dict
        sample_keys = list(all_holidays.keys())[:5] if all_holidays else []
        if sample_keys:
            print(f"     Sample dict keys (first 5): {sample_keys}")
            print(f"     Key types: {[type(k).__name__ for k in sample_keys]}")
            # Check if Christmas date exists
            xmas_date = date_only + timedelta(days=11)  # Dec 25
            print(f"     Checking for {xmas_date} (Christmas)...")
            print(f"       As date object: {xmas_date in all_holidays}")
            print(f"       As string: {'2025-12-25' in all_holidays}")
            if xmas_date in all_holidays:
                print(f"       ✅ Found: {all_holidays[xmas_date]}")
            elif '2025-12-25' in all_holidays:
                print(f"       ✅ Found with string key: {all_holidays['2025-12-25']}")
        
        found_holidays = []
        for i in range(1, 31):
            check_date = date_only + timedelta(days=i)
            check_date_str = check_date.strftime('%Y-%m-%d')
            # Try both date object and string
            if check_date in all_holidays:
                holiday_name = all_holidays[check_date]
                found_holidays.append((i, check_date_str, holiday_name))
                print(f"     Day {i} ({check_date_str}): {holiday_name}")
            elif check_date_str in all_holidays:
                holiday_name = all_holidays[check_date_str]
                found_holidays.append((i, check_date_str, holiday_name))
                print(f"     Day {i} ({check_date_str}) [string key]: {holiday_name}")
        
        if found_holidays:
            print(f"\n     Found {len(found_holidays)} holiday(s) in range")
            for days, date_str, name in found_holidays:
                print(f"       - {name} on {date_str} (day {days})")
        else:
            print(f"     ❌ No holidays found in date range!")
    except Exception as e:
        print(f"     ❌ Error tracing: {e}")
        import traceback
        traceback.print_exc()
    
    upcoming = get_upcoming_holidays(now, days_ahead=30)
    if upcoming:
        for holiday in upcoming:
            days = holiday['days_until']
            name = holiday['name']
            date = holiday['date']
            print(f"  🎄 {name}")
            print(f"     Days until: {days}")
            print(f"     Date: {date}")
            if days == 1:
                print(f"     → Tomorrow!")
            elif days <= 7:
                print(f"     → This week!")
            elif days <= 14:
                print(f"     → Within 2 weeks")
    else:
        print("  ❌ No upcoming holidays found in next 30 days")
        print("\n  🔍 Debugging...")
        
        # Try checking manually for Christmas
        christmas_2025 = datetime(2025, 12, 25, tzinfo=LOCATION_TZ)
        days_until_xmas = (christmas_2025.date() - now.date()).days
        print(f"\n  Manual check for Christmas 2025:")
        print(f"     Date: {christmas_2025.date()}")
        print(f"     Days until: {days_until_xmas}")
        
        if days_until_xmas > 0 and days_until_xmas <= 30:
            print(f"     ⚠️  Christmas should be detected but wasn't!")
            
            # Try importing holidays library directly
            try:
                import holidays
                us_holidays = holidays.UnitedStates(years=[2025])
                la_holidays = holidays.US(state='LA', years=[2025])
                
                xmas_str = christmas_2025.strftime('%Y-%m-%d')
                print(f"\n  Direct library check for {xmas_str}:")
                if xmas_str in us_holidays:
                    print(f"     US Holiday: {us_holidays[xmas_str]}")
                if xmas_str in la_holidays:
                    print(f"     LA Holiday: {la_holidays[xmas_str]}")
                    
                # Check what the filter would do
                holiday_name = us_holidays.get(xmas_str, la_holidays.get(xmas_str, None))
                if holiday_name:
                    print(f"\n  Filter check:")
                    print(f"     Holiday name: '{holiday_name}'")
                    major_holidays = [
                        'Christmas', 'New Year', 'Thanksgiving', 'Independence Day',
                        'Memorial Day', 'Labor Day', 'Veterans Day', 'Presidents Day',
                        'Martin Luther King', 'Easter', 'Halloween', 'Valentine',
                        'Mardi Gras', 'New Year\'s Day', 'Christmas Day', 'New Year\'s Eve'
                    ]
                    holiday_lower = holiday_name.lower()
                    matches = [m for m in major_holidays if m.lower() in holiday_lower]
                    if matches:
                        print(f"     ✅ Would match: {matches}")
                    else:
                        print(f"     ❌ Would NOT match any major holiday keywords")
                        print(f"     Keywords checked: {major_holidays}")
            except ImportError:
                print(f"     ❌ Holidays library not available!")
            except Exception as e:
                print(f"     ❌ Error checking library: {e}")
    
    # Test with metadata context
    print("\n" + "-" * 80)
    print("FULL CONTEXT METADATA:")
    print("-" * 80)
    metadata = get_context_metadata(observation_type="evening")
    print(f"  Holidays today: {metadata.get('holidays', [])}")
    print(f"  Is holiday: {metadata.get('is_holiday', False)}")
    print(f"  Upcoming holidays: {metadata.get('upcoming_holidays', [])}")
    
    # Test formatted context
    print("\n" + "-" * 80)
    print("FORMATTED CONTEXT FOR PROMPT:")
    print("-" * 80)
    formatted = format_context_for_prompt(metadata)
    print(formatted)
    
    # Test with a specific date (Dec 13, 2025 - when the simulation ran)
    print("\n" + "=" * 80)
    print("TESTING WITH SIMULATION DATE (Dec 13, 2025):")
    print("=" * 80)
    sim_date = datetime(2025, 12, 13, 23, 42, 0, tzinfo=LOCATION_TZ)
    print(f"\n📅 Simulation Date: {sim_date.strftime('%B %d, %Y at %I:%M %p %Z')}")
    
    sim_upcoming = get_upcoming_holidays(sim_date, days_ahead=30)
    if sim_upcoming:
        print("\n  Upcoming holidays from simulation date:")
        for holiday in sim_upcoming:
            print(f"    🎄 {holiday['name']} in {holiday['days_until']} days ({holiday['date']})")
    else:
        print("\n  ❌ No upcoming holidays found from simulation date")
    
    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    test_holiday_detection()

