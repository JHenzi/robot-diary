"""Generate Hugo blog posts and build the site."""
import subprocess
from pathlib import Path
from datetime import datetime
import shutil
import logging

from ..config import (
    HUGO_SITE_PATH, 
    HUGO_CONTENT_DIR, 
    HUGO_STATIC_IMAGES_DIR, 
    HUGO_BUILD_ON_UPDATE,
    HUGO_PUBLIC_DIR,
    DEPLOY_ENABLED,
    DEPLOY_METHOD,
    DEPLOY_DESTINATION,
    DEPLOY_SSH_KEY
)
from ..context.metadata import LOCATION_TZ

logger = logging.getLogger(__name__)


class HugoGenerator:
    """Generate Hugo posts and manage site builds."""
    
    def __init__(self):
        self.content_dir = HUGO_CONTENT_DIR
        self.static_images_dir = HUGO_STATIC_IMAGES_DIR
    
    def create_post(self, diary_entry: str, image_path: Path, observation_id: int, 
                   context_metadata: dict = None, is_news_based: bool = False) -> Path:
        """
        Create a Hugo blog post from a diary entry.
        
        Args:
            diary_entry: The diary entry text
            image_path: Path to the source image (or placeholder for news-based)
            observation_id: Unique observation ID
            context_metadata: Context metadata for title generation
            is_news_based: If True, this is a news-based observation (no image)
            
        Returns:
            Path to the created post file
        """
        # Generate title from context metadata first (needed for image filename)
        post_title = ""
        if context_metadata:
            from ..context.metadata import format_date_for_title
            try:
                post_title = format_date_for_title(context_metadata)
                # If news-based, add indicator to title
                if is_news_based and context_metadata.get('news_cluster'):
                    topic = context_metadata['news_cluster'].get('topic_label', 'Transmission')
                    post_title = f"{post_title} - Transmission: {topic}"
            except Exception as e:
                logger.warning(f"Error formatting title: {e}, using fallback")
                post_title = datetime.now(LOCATION_TZ).strftime('%A %B %d, %Y')
        else:
            # Fallback to simple date if no metadata
            post_title = datetime.now(LOCATION_TZ).strftime('%A %B %d, %Y')
        
        # Copy image to Hugo static directory (if not news-based)
        image_markdown = ""
        if not is_news_based and image_path and image_path.exists():
            image_filename = f"observation_{observation_id}_{image_path.name}"
            dest_image_path = self.static_images_dir / image_filename
            shutil.copy2(image_path, dest_image_path)
            logger.info(f"✅ Image copied to Hugo static: {dest_image_path}")
            image_markdown = f"![{post_title}](/images/{image_filename})\n\n"
        elif is_news_based:
            logger.info("News-based observation: No image to copy")
        
        # Generate post filename with timestamp to avoid collisions
        # Format: YYYY-MM-DD_HHMMSS_observation_N.md
        # Use location timezone to ensure correct date
        timestamp = datetime.now(LOCATION_TZ).strftime('%Y-%m-%d_%H%M%S')
        post_filename = f"{timestamp}_observation_{observation_id}.md"
        post_path = self.content_dir / post_filename
        
        # Check if file already exists (shouldn't happen, but safety check)
        if post_path.exists():
            logger.warning(f"Post file already exists: {post_path}, appending timestamp")
            timestamp = datetime.now(LOCATION_TZ).strftime('%Y-%m-%d_%H%M%S_%f')[:-3]  # Add microseconds
            post_filename = f"{timestamp}_observation_{observation_id}.md"
            post_path = self.content_dir / post_filename
        
        # Create front matter and content
        from ..config import ROBOT_NAME
        tags = ["robot-diary", "observation", "b3n-t5-mnt"]
        if is_news_based:
            tags.append("news-transmission")
        
        # Add cover image to front matter if we have an image
        # Cover shows in list view (for previews) but hidden in single post view (to avoid duplication with inline image)
        cover_image_param = ""
        if not is_news_based and image_path and image_path.exists():
            # Image filename for cover (relative to /images/)
            image_filename = f"observation_{observation_id}_{image_path.name}"
            cover_image_param = f'cover.image = "/images/{image_filename}"\ncover.alt = "{post_title}"\ncover.hidden = false\ncover.hiddenInList = false\ncover.hiddenInSingle = true\n'
        
        # Use location timezone for front matter date
        now_local = datetime.now(LOCATION_TZ)
        # Format timezone offset (e.g., -0600 for CST, -0500 for CDT)
        tz_offset = now_local.strftime('%z')
        if not tz_offset:
            # Fallback if timezone offset not available
            tz_offset = '-0600'  # Default to CST
        date_str = now_local.strftime(f'%Y-%m-%dT%H:%M:%S{tz_offset}')
        
        front_matter = f"""+++
date = "{date_str}"
draft = false
title = "{post_title}"
tags = {tags}
{cover_image_param}+++

"""
        
        # Combine front matter, image (if any), and diary entry
        post_content = front_matter + image_markdown + diary_entry
        
        # Write post
        with open(post_path, 'w', encoding='utf-8') as f:
            f.write(post_content)
        
        logger.info(f"✅ Hugo post created: {post_path}")
        return post_path
    
    def build_site(self) -> bool:
        """
        Build the Hugo site.
        
        Returns:
            True if build successful, False otherwise
        """
        if not HUGO_BUILD_ON_UPDATE:
            logger.info("Hugo build disabled (HUGO_BUILD_ON_UPDATE=false)")
            return False
        
        logger.info(f"Building Hugo site at {HUGO_SITE_PATH}...")
        
        try:
            result = subprocess.run(
                ['hugo', '--cleanDestinationDir'],
                cwd=HUGO_SITE_PATH,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("✅ Hugo site built successfully")
            logger.debug(f"Hugo output: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Hugo build failed: {e}")
            logger.error(f"Hugo error output: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("❌ Hugo not found. Is Hugo installed?")
            return False
    
    def deploy_site(self) -> bool:
        """
        Deploy the built Hugo site to remote server.
        
        Uses rsync or scp based on DEPLOY_METHOD configuration.
        
        Returns:
            True if deployment successful, False otherwise
        """
        if not DEPLOY_ENABLED:
            logger.info("Deployment disabled (DEPLOY_ENABLED=false)")
            return False
        
        if not DEPLOY_DESTINATION:
            logger.warning("Deployment enabled but DEPLOY_DESTINATION not set")
            return False
        
        if not HUGO_PUBLIC_DIR.exists():
            logger.error(f"❌ Hugo public directory not found: {HUGO_PUBLIC_DIR}")
            logger.error("Build the site first before deploying")
            return False
        
        logger.info(f"Deploying site to {DEPLOY_DESTINATION} using {DEPLOY_METHOD}...")
        
        try:
            if DEPLOY_METHOD == 'rsync':
                # Use rsync for efficient deployment
                cmd = ['rsync', '-avz', '--delete']
                
                # Exclude files that should be preserved on destination
                cmd.extend(['--exclude', 'log.html'])  # Preserve log.html on destination
                
                # Add SSH key if specified
                if DEPLOY_SSH_KEY:
                    # Use fixed container path (key is mounted from .env)
                    ssh_key_path = '/app/.ssh/deploy_key'
                    
                    # Fix permissions (SSH requires 600 for private keys)
                    try:
                        import os
                        os.chmod(ssh_key_path, 0o600)
                    except Exception as e:
                        logger.warning(f"Could not set key permissions: {e}")
                    
                    # SSH options for non-interactive deployment:
                    # - StrictHostKeyChecking=accept-new: Accept new host keys automatically (but still validate)
                    # - UserKnownHostsFile: Save to known_hosts for future connections
                    ssh_opts = f"-i {ssh_key_path} -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/app/.ssh/known_hosts"
                    cmd.extend(['-e', f'ssh {ssh_opts}'])
                
                # Source and destination
                cmd.append(f"{HUGO_PUBLIC_DIR}/")
                cmd.append(f"{DEPLOY_DESTINATION}/")
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info("✅ Site deployed successfully via rsync")
                logger.debug(f"Rsync output: {result.stdout}")
                return True
                
            elif DEPLOY_METHOD == 'scp':
                # Use scp (less efficient but simpler)
                cmd = ['scp', '-r']
                
                # Add SSH key if specified
                if DEPLOY_SSH_KEY:
                    # Use fixed container path (key is mounted from .env)
                    ssh_key_path = '/app/.ssh/deploy_key'
                    
                    # Fix permissions (SSH requires 600 for private keys)
                    try:
                        import os
                        os.chmod(ssh_key_path, 0o600)
                    except Exception as e:
                        logger.warning(f"Could not set key permissions: {e}")
                    
                    # SSH options for non-interactive deployment
                    cmd.extend(['-i', ssh_key_path, '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=/app/.ssh/known_hosts'])
                
                # Source and destination
                cmd.append(f"{HUGO_PUBLIC_DIR}/*")
                cmd.append(DEPLOY_DESTINATION)
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info("✅ Site deployed successfully via scp")
                logger.debug(f"Scp output: {result.stdout}")
                return True
            else:
                logger.error(f"❌ Unknown deployment method: {DEPLOY_METHOD}")
                logger.error("Supported methods: 'rsync' or 'scp'")
                return False
                
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Deployment failed: {e}")
            logger.error(f"Error output: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error(f"❌ {DEPLOY_METHOD} not found. Is it installed?")
            return False

