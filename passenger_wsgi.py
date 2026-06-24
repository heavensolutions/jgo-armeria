#!/usr/bin/env python3
"""
passenger_wsgi.py — CPanel Passenger entry point for JGO Armeria.

CPanel's "Setup Python App" uses mod_passenger (Phusion Passenger),
which expects a file called `passenger_wsgi.py` in the app root.

This file initializes the application and sets up the environment
before delegating to the Flask app.
"""
import os
import sys

# Ensure the app directory is on the path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Set environment variables from .env if present
env_file = os.path.join(APP_DIR, '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            # Remove quotes if present
            if len(value) > 1 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            os.environ.setdefault(key, value)

# Import and create the Flask app
from app import app as application

# For local testing
if __name__ == "__main__":
    application.run()
