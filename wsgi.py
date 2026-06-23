#!/usr/bin/env python3
"""WSGI entry point for gunicorn/production."""
from app import app

if __name__ == "__main__":
    app.run()
