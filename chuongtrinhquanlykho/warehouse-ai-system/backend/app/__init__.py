"""
app/__init__.py — Package init cho app
========================================
Expose create_app để Flask CLI và tests có thể import.

Khi chạy: flask --app app run
Flask sẽ tìm create_app() trong app/__init__.py hoặc app/main.py
"""

from app.main import create_app

__all__ = ["create_app"]
