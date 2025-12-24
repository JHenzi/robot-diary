#!/usr/bin/env python
"""
Entry point for Robot Diary Service.

Run with: python run_service.py
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.service import main

if __name__ == '__main__':
    main()

