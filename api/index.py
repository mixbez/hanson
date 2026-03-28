"""Vercel serverless entry point."""
import sys
import os

# Add project root to path so `hanson` package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
