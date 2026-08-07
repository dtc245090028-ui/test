"""
auth/__init__.py — Package auth
================================
Export Blueprint để main.py import và đăng ký.
"""

from app.auth.routes import auth_bp

__all__ = ["auth_bp"]
