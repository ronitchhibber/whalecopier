#!/usr/bin/env python3
"""
Run database migrations
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from alembic.config import Config
from alembic import command

# Get the alembic.ini path
alembic_cfg = Config("alembic.ini")

# Run upgrade to head
print("Running database migrations...")
command.upgrade(alembic_cfg, "head")
print("✅ Migration complete!")
