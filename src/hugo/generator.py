"""Generate Hugo blog posts and build the site."""
import subprocess
from pathlib import Path
from datetime import datetime
import shutil
import logging
import re

from ..config import (
    HUGO_SITE_PATH, 
    HUGO_CONTENT_DIR, 
    HUGO_STATIC_IMAGES_DIR, 
    HUGO_BUILD_ON_UPDATE,
    HUGO_PUBLIC_DIR,
    DEPLOY_ENABLED,
    DEPLOY_METHOD,
    DEPLOY_DESTINATION,
    DEPLOY_SSH_KEY,
    DEPLOY_HOST_IP
)
from ..context.metadata import LOCATION_TZ

logger = logging.getLogger(__name__)


class HugoGenerator:
    """Generate Hugo posts and manage site builds."""
    
    def __init__(self):
        self.content_dir = HUGO_CONTENT_DIR
        self.static_images_dir = HUGO_STATIC_IMAGES_DIR
    
    def _get_observation_slug(self, observation_id: int) -> str | None:
        """
        Get the Hugo post slug (filename without extension) for a given observation ID.
        
        This uses basic pattern matching on existing post filenames, without any LLM calls.
        If multiple posts exist for the same observation ID, the earliest (by filename sort)
        is returned to keep behavior stable and deterministic.
        """
        try:
            matching_files = sorted(self.content_dir.glob(f"*_observation_{observation_id}.md"))
            if not matching_files:
                return None
            return matching_files[0].stem
        except Exception as e:
            logger.warning(f"Error looking up slug for observation {observation_id}: {e}")
            return None
    
    def _link_observation_references(self, diary_entry: str) -> str:
        """
        Post-process diary text to turn references like 'Observation #45' or '#45'
        into markdown links pointing at the matching observation post.
        
        This uses simple regex-based pattern matching and filesystem lookups only.
        Matches both "Observation #NN" and standalone "#NN" patterns.
        """
        # Match:
        #   - "Observation #45"
        #   - "Observation #45" (with non-breaking space)
        #   - allow optional extra whitespace around '#'
        # First, fix malformed markdown headers like "##[# 1]" -> "## 1"
        # This pattern occurs when the LLM generates headers with links incorrectly
        # Handles both "##[# 1]" (with space) and "##[#1]" (without space)
        # Also remove links from headers that are already linked like "## [1](/posts/...)" -> "## 1"
        result = re.sub(r'^(##+)\[#\s*(\d+)\]', r'\1 \2', diary_entry, flags=re.MULTILINE)
        result = re.sub(r'^(##+)\s*\[(\d+)\]\(/posts/[^)]+\)', r'\1 \2', result, flags=re.MULTILINE)
        
        # Pattern 1: "Observation #NN" (with various space types)
        # Process this first to avoid double-matching
        obs_pattern = re.compile(r"(Observation[\u00A0\u202F ]*#\s*(\d+))")
        
        def replace_obs(match: re.Match) -> str:
            full_text = match.group(1)
            obs_id_str = match.group(2)
            try:
                obs_id = int(obs_id_str)
            except ValueError:
                return full_text
            
            slug = self._get_observation_slug(obs_id)
            if not slug:
                return full_text
            
            return f"[{full_text}](/posts/{slug})"
        
        result = obs_pattern.sub(replace_obs, result)
        
        # Pattern 2: Standalone "#NN" (not part of markdown headers and not already linked)
        # Use negative lookbehind to avoid matching "#NN" that's part of "Observation #NN" or already in a link
        # Exclude headers by ensuring we're not on a line that starts with "##" followed by our pattern
        # Use word boundary or non-word char after to ensure we match the full number
        # Process line by line to avoid matching headers
        lines = result.split('\n')
        processed_lines = []
        for line in lines:
            # Skip processing if this line is a markdown header (starts with ##)
            if re.match(r'^##+\s', line):
                processed_lines.append(line)
            else:
                # Only process standalone #NN patterns on non-header lines
                standalone_pattern = re.compile(r"(?<!Observation[\u00A0\u202F ])(?<!\[)(?<![a-zA-Z])#\s*(\d+)(?=\s|$|[^\d])")
                
                def replace_standalone(match: re.Match) -> str:
                    full_text = match.group(0)  # The entire match including "#"
                    obs_id_str = match.group(1)
                    try:
                        obs_id = int(obs_id_str)
                    except ValueError:
                        return full_text
                    
                    slug = self._get_observation_slug(obs_id)
                    if not slug:
                        return full_text
                    
                    return f"[{full_text}](/posts/{slug})"
                
                processed_lines.append(standalone_pattern.sub(replace_standalone, line))
        
        result = '\n'.join(processed_lines)
        
        return result
    
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
        
        # Copy image to Hugo static and assets directories (if not news-based)
        # Assets directory allows Hugo to process/resize images
        image_markdown = ""
        if not is_news_based and image_path and image_path.exists():
            image_filename = f"observation_{observation_id}_{image_path.name}"
            # Copy to static (for backward compatibility and direct access)
            dest_image_path = self.static_images_dir / image_filename
            shutil.copy2(image_path, dest_image_path)
            logger.info(f"✅ Image copied to Hugo static: {dest_image_path}")
            
            # Also copy to assets for Hugo image processing
            assets_images_dir = HUGO_SITE_PATH / 'assets' / 'images'
            assets_images_dir.mkdir(parents=True, exist_ok=True)
            assets_image_path = assets_images_dir / image_filename
            shutil.copy2(image_path, assets_image_path)
            logger.info(f"✅ Image copied to Hugo assets: {assets_image_path}")
            
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
        
        # Post-process diary entry to link any explicit references to past observations
        processed_diary_entry = self._link_observation_references(diary_entry)
        
        # Combine front matter, image (if any), and processed diary entry
        post_content = front_matter + image_markdown + processed_diary_entry
        
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
            # Build with production environment to enable image processing
            result = subprocess.run(
                ['hugo', '--cleanDestinationDir', '--minify', '--environment', 'production'],
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
        
        # If DEPLOY_HOST_IP is set, replace hostname in DEPLOY_DESTINATION with IP
        # This allows using IP directly instead of domain (useful when DNS points to different IP)
        deploy_destination = DEPLOY_DESTINATION
        if DEPLOY_HOST_IP:
            # Replace hostname with IP: user@host:/path -> user@IP:/path
            deploy_destination = re.sub(r'@([^:/]+)', f'@{DEPLOY_HOST_IP}', DEPLOY_DESTINATION)
            logger.info(f"Using IP address {DEPLOY_HOST_IP} instead of hostname in destination")
        
        logger.info(f"Deploying site to {deploy_destination} using {DEPLOY_METHOD}...")
        
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
                    # - F: Use SSH config file for host aliases
                    # - StrictHostKeyChecking=accept-new: Accept new host keys automatically (but still validate)
                    # - UserKnownHostsFile: Save to known_hosts for future connections
                    ssh_opts = f"-F /app/.ssh/config -i {ssh_key_path} -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/app/.ssh/known_hosts"
                    cmd.extend(['-e', f'ssh {ssh_opts}'])
                
                # Source and destination
                cmd.append(f"{HUGO_PUBLIC_DIR}/")
                cmd.append(f"{deploy_destination}/")
                
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
                    # -F: Use SSH config file for host aliases
                    cmd.extend(['-F', '/app/.ssh/config', '-i', ssh_key_path, '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=/app/.ssh/known_hosts'])
                
                # Source and destination
                cmd.append(f"{HUGO_PUBLIC_DIR}/*")
                cmd.append(deploy_destination)
                
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

