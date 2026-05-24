"""
Initialize default worker configurations in the database.
Also provides a CLI to enable/disable workers.
"""

import sys
import os
import argparse
from sqlalchemy.orm import Session

# Add current dir to path to import shared_core
sys.path.insert(0, os.getcwd())

from shared_core import models, database

def initialize_configs(reset=False):
    db = database.SessionLocal()
    
    # List of all known worker types
    worker_types = [
        ("review", "Video Review Worker - Analyzes videos using AI"),
        ("unbox", "Unbox Worker - Viral video generation"),
        ("research", "Research Worker - Searches and analyzes social media"),
        ("slideshow", "Slideshow Worker - Creates video from images"),
        ("download", "Download Worker - Social media downloader"),
        ("promotion", "Promotion Worker - Ad video generator"),
        ("agent", "Agent Orchestrator - High-level AI coordination"),
        ("leader", "AI Leader Agent - Analyzes scripts and orchestrates workflows"),
        ("translify", "Translify Worker - Chinese-to-Vietnamese translator"),
        ("text2img", "Text-to-Image Worker - Generates images via ComfyUI (FLUX)"),
        ("tts", "Text-to-Speech Worker - Generates Vietnamese audio from text"),
    ]
    
    if reset:
        print("Resetting all worker configurations...")
        db.query(models.WorkerConfig).delete()
        db.commit()
    
    count = 0
    for wtype, desc in worker_types:
        existing = db.query(models.WorkerConfig).filter(models.WorkerConfig.worker_type == wtype).first()
        if not existing:
            config = models.WorkerConfig(
                worker_type=wtype,
                is_enabled=True, # Default to True for now so dev environment works immediately
                config_data={"description": desc}
            )
            db.add(config)
            count += 1
            print(f"Created config for '{wtype}'")
    
    db.commit()
    db.close()
    print(f"Done. Initialized {count} new worker configs.")

def set_worker_status(worker_type, enabled):
    db = database.SessionLocal()
    config = db.query(models.WorkerConfig).filter(models.WorkerConfig.worker_type == worker_type).first()
    if config:
        config.is_enabled = enabled
        db.commit()
        status = "ENABLED" if enabled else "DISABLED"
        print(f"Worker '{worker_type}' is now {status}")
    else:
        print(f"Error: Worker '{worker_type}' not found.")
    db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worker Management CLI")
    parser.add_argument("--init", action="store_true", help="Initialize default configs")
    parser.add_argument("--reset", action="store_true", help="Delete all and re-initialize")
    parser.add_argument("--enable", type=str, help="Enable a worker type")
    parser.add_argument("--disable", type=str, help="Disable a worker type")
    parser.add_argument("--list", action="store_true", help="List all worker configs")
    
    args = parser.parse_args()
    
    if args.reset or args.init:
        initialize_configs(reset=args.reset)
    elif args.enable:
        set_worker_status(args.enable, True)
    elif args.disable:
        set_worker_status(args.disable, False)
    elif args.list:
        db = database.SessionLocal()
        configs = db.query(models.WorkerConfig).all()
        print("\n--- Worker Configurations ---")
        for c in configs:
            status = "ON " if c.is_enabled else "OFF"
            print(f"[{status}] {c.worker_type:<15}")
        db.close()
    else:
        parser.print_help()
