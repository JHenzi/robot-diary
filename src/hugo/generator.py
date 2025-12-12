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

logger = logging.getLogger(__name__)


class HugoGenerator:
    """Generate Hugo posts and manage site builds."""
    
    def __init__(self):
        self.content_dir = HUGO_CONTENT_DIR
        self.static_images_dir = HUGO_STATIC_IMAGES_DIR
    
    def create_post(self, diary_entry: str, image_path: Path, observation_id: int, 
                   context_metadata: dict = None) -> Path:
        """
        Create a Hugo blog post from a diary entry.
        
        Args:
            diary_entry: The diary entry text
            image_path: Path to the source image
            observation_id: Unique observation ID
            context_metadata: Context metadata for title generation
            
        Returns:
            Path to the created post file
        """
        # Copy image to Hugo static directory
        image_filename = f"observation_{observation_id}_{image_path.name}"
        dest_image_path = self.static_images_dir / image_filename
        shutil.copy2(image_path, dest_image_path)
        logger.info(f"✅ Image copied to Hugo static: {dest_image_path}")
        
        # Generate post filename
        timestamp = datetime.now().strftime('%Y-%m-%d')
        post_filename = f"{timestamp}_observation_{observation_id}.md"
        post_path = self.content_dir / post_filename
        
        # Generate title from context metadata
        if context_metadata:
            from ..context.metadata import format_date_for_title
            try:
                post_title = format_date_for_title(context_metadata)
            except Exception as e:
                logger.warning(f"Error formatting title: {e}, using fallback")
                post_title = datetime.now().strftime('%A %B %d, %Y')
        else:
            # Fallback to simple date if no metadata
            post_title = datetime.now().strftime('%A %B %d, %Y')
        
        # Create front matter and content
        from ..config import ROBOT_NAME
        front_matter = f"""+++
date = {datetime.now().strftime('"%Y-%m-%dT%H:%M:%S%z"')}
draft = false
title = "{post_title}"
tags = ["robot-diary", "observation", "b3n-t5-mnt"]
+++

"""
        
        # Add image to content
        image_markdown = f"![{post_title}](/images/{image_filename})\n\n"
        
        # Combine front matter, image, and diary entry
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
                ['hugo'],
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
                
                # Add SSH key if specified
                if DEPLOY_SSH_KEY:
                    cmd.extend(['-e', f'ssh -i {DEPLOY_SSH_KEY}'])
                
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
                    cmd.extend(['-i', DEPLOY_SSH_KEY])
                
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

