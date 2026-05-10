#!/usr/bin/env python3
"""
Scheduled task runner + Vercel auto-deploy
Runs at 7:00 AM daily, generates brief, deploys to cloud
"""

import sys
import os
import logging
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_config, get_output_paths, AppConfig
from src.utils import setup_logging, get_today_str

logger = logging.getLogger(__name__)

# Vercel CLI path
VERCEL_CLI = "vercel"


def get_yesterday_str() -> str:
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def deploy_to_vercel(output_dir: str):
    """Deploy output directory to Vercel"""
    if not os.path.exists(output_dir):
        logger.warning(f"Output directory not found: {output_dir}")
        return False
    
    try:
        logger.info("Deploying to Vercel...")
        result = subprocess.run(
            [VERCEL_CLI, "--prod", "--yes"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            # Extract URL from output
            for line in result.stdout.splitlines():
                if "https://" in line:
                    logger.info(f"  Deployed: {line.strip()}")
            return True
        else:
            logger.error(f"Vercel deploy failed: {result.stderr}")
            return False
    except FileNotFoundError:
        logger.warning("Vercel CLI not found. Install with: npm i -g vercel")
        logger.warning("Skipping cloud deployment. Brief saved locally.")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Vercel deploy timed out")
        return False


def run_scheduled_task(config_path: str = "config.yaml", text_only: bool = False,
                       deploy: bool = False):
    """
    Execute scheduled task: generate yesterday's brief, optionally deploy
    """
    setup_logging(logging.INFO)
    
    target_date = get_yesterday_str()
    
    logger.info("=" * 60)
    logger.info(f"Scheduled task started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Processing date: {target_date}")
    logger.info("=" * 60)
    
    try:
        config = load_config(config_path)
        
        from main import run_pipeline
        
        stats = run_pipeline(config, target_date, text_only)
        
        if stats["success"]:
            logger.info("Brief generated successfully!")
            logger.info(f"  HTML: {stats.get('html_output', 'N/A')}")
            logger.info(f"  Markdown: {stats.get('text_output', 'N/A')}")
            if stats.get('audio_output'):
                logger.info(f"  Audio: {stats['audio_output']}")
            
            # Auto deploy to Vercel
            if deploy:
                output_dir = str(Path(stats.get('html_output', '')).parent)
                if output_dir:
                    deploy_to_vercel(output_dir)
        else:
            logger.error(f"Task failed: {stats.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Task error: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Brief Scheduler")
    parser.add_argument("--config", "-c", default="config.yaml", help="Config file path")
    parser.add_argument("--text-only", action="store_true", help="Text only, no audio")
    parser.add_argument("--deploy", action="store_true", help="Deploy to Vercel after generation")
    args = parser.parse_args()
    
    run_scheduled_task(args.config, args.text_only, args.deploy)
