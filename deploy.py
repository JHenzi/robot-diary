#!/usr/bin/env python3
"""
Deploy Hugo site to remote server using rsync.

This script builds the Hugo site and deploys it to the configured
remote destination using rsync with delete option.
"""
import subprocess
import sys
import os
from pathlib import Path

from src.config import (
    HUGO_SITE_PATH,
    HUGO_PUBLIC_DIR,
    DEPLOY_ENABLED,
    DEPLOY_METHOD,
    DEPLOY_DESTINATION,
    DEPLOY_SSH_KEY
)


def build_hugo():
    """Build the Hugo site."""
    print("🔨 Building Hugo site...")
    try:
        result = subprocess.run(
            ['hugo'],
            cwd=HUGO_SITE_PATH,
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Hugo build successful")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Hugo build failed: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Hugo not found. Is Hugo installed?")
        return False


def deploy_with_rsync():
    """Deploy using rsync."""
    if not DEPLOY_DESTINATION:
        print("❌ DEPLOY_DESTINATION not configured in .env")
        return False
    
    print(f"📤 Deploying to {DEPLOY_DESTINATION}...")
    
    # Build rsync command
    rsync_cmd = [
        'rsync',
        '-avz',  # archive, verbose, compress
        '--delete',  # delete files on remote that don't exist locally
        '--exclude', '.DS_Store',  # exclude macOS files
        '--exclude', '*.swp',  # exclude vim swap files
        '--exclude', '.git',  # exclude git files
        '--exclude', 'log.html',  # preserve log.html on destination (don't overwrite)
    ]
    
    # Add SSH key if specified
    if DEPLOY_SSH_KEY:
        rsync_cmd.extend(['-e', f'ssh -i {DEPLOY_SSH_KEY}'])
        print(f"   Using SSH key: {DEPLOY_SSH_KEY}")
    
    # Add source and destination
    source = str(HUGO_PUBLIC_DIR) + '/'
    rsync_cmd.extend([source, DEPLOY_DESTINATION])
    
    print(f"   Source: {source}")
    print(f"   Destination: {DEPLOY_DESTINATION}")
    print(f"   Command: {' '.join(rsync_cmd)}")
    print()
    
    try:
        result = subprocess.run(
            rsync_cmd,
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Deployment successful!")
        if result.stdout:
            # Show summary of transferred files
            lines = result.stdout.strip().split('\n')
            for line in lines[-10:]:  # Show last 10 lines
                if line.strip():
                    print(f"   {line}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Deployment failed: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ rsync not found. Is rsync installed?")
        return False


def deploy_with_scp():
    """Deploy using scp (legacy method, not recommended for directories)."""
    print("⚠️  SCP method is not recommended for directory deployment.")
    print("   Please use rsync instead (set DEPLOY_METHOD=rsync in .env)")
    return False


def main():
    """Main deployment function."""
    print("=" * 60)
    print("🚀 Robot Diary - Site Deployment")
    print("=" * 60)
    print()
    
    # Check if deployment is enabled
    if not DEPLOY_ENABLED:
        print("⚠️  Deployment is disabled in .env (DEPLOY_ENABLED=false)")
        print("   Set DEPLOY_ENABLED=true to enable deployment")
        sys.exit(1)
    
    # Check if public directory exists
    if not HUGO_PUBLIC_DIR.exists():
        print(f"⚠️  Public directory not found: {HUGO_PUBLIC_DIR}")
        print("   Building Hugo site first...")
    
    # Build Hugo
    if not build_hugo():
        sys.exit(1)
    
    print()
    
    # Deploy based on method
    if DEPLOY_METHOD == 'rsync':
        success = deploy_with_rsync()
    elif DEPLOY_METHOD == 'scp':
        success = deploy_with_scp()
    else:
        print(f"❌ Unknown deployment method: {DEPLOY_METHOD}")
        print("   Use 'rsync' or 'scp' in DEPLOY_METHOD")
        sys.exit(1)
    
    if not success:
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("✅ Deployment complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

