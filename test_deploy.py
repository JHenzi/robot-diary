#!/usr/bin/env python
"""
Quick test script to test deployment from inside the container.
"""
import sys
from pathlib import Path

# Add project root to path so we can import from src
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.hugo.generator import HugoGenerator
from src.config import DEPLOY_ENABLED, DEPLOY_DESTINATION, DEPLOY_HOST_IP

def main():
    print("=" * 60)
    print("🧪 Testing Deployment")
    print("=" * 60)
    print()
    
    if not DEPLOY_ENABLED:
        print("❌ Deployment is disabled (DEPLOY_ENABLED=false)")
        print("   Set DEPLOY_ENABLED=true in .env")
        return 1
    
    print(f"📋 Configuration:")
    print(f"   Destination: {DEPLOY_DESTINATION}")
    if DEPLOY_HOST_IP:
        print(f"   Using IP: {DEPLOY_HOST_IP}")
    else:
        print(f"   ⚠️  No DEPLOY_HOST_IP set - will use hostname from DEPLOY_DESTINATION")
    print()
    
    # Build first
    print("🔨 Building Hugo site...")
    generator = HugoGenerator()
    build_success = generator.build_site()
    
    if not build_success:
        print("❌ Build failed, skipping deployment")
        return 1
    
    print()
    print("🚀 Deploying site...")
    deploy_success = generator.deploy_site()
    
    if deploy_success:
        print()
        print("=" * 60)
        print("✅ Deployment test successful!")
        print("=" * 60)
        return 0
    else:
        print()
        print("=" * 60)
        print("❌ Deployment test failed")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())

