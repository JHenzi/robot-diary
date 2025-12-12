"""Generate Hugo blog posts and build the site."""
import subprocess
from pathlib import Path
from datetime import datetime
import shutil
import logging

from ..config import HUGO_SITE_PATH, HUGO_CONTENT_DIR, HUGO_STATIC_IMAGES_DIR, HUGO_BUILD_ON_UPDATE

logger = logging.getLogger(__name__)


class HugoGenerator:
    """Generate Hugo posts and manage site builds."""
    
    def __init__(self):
        self.content_dir = HUGO_CONTENT_DIR
        self.static_images_dir = HUGO_STATIC_IMAGES_DIR
    
    def create_post(self, diary_entry: str, image_path: Path, observation_id: int) -> Path:
        """
        Create a Hugo blog post from a diary entry.
        
        Args:
            diary_entry: The diary entry text
            image_path: Path to the source image
            observation_id: Unique observation ID
            
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
        
        # Create front matter and content
        from ..config import ROBOT_NAME
        front_matter = f"""+++
date = {datetime.now().strftime('"%Y-%m-%dT%H:%M:%S%z"')}
draft = false
title = "{ROBOT_NAME} - Observation #{observation_id}"
tags = ["robot-diary", "observation", "b3n-t5-mnt"]
+++

"""
        
        # Add image to content
        image_markdown = f"![{ROBOT_NAME} - Observation #{observation_id}](/images/{image_filename})\n\n"
        
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

