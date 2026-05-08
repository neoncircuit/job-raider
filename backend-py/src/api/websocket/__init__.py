"""
Job Raider - WebSocket Module

WebSocket handlers for real-time pipeline progress updates.

Author: Job Raider
Date: 2026-04-21
"""

from .progress import ConnectionManager, manager

__all__ = ["ConnectionManager", "manager"]
