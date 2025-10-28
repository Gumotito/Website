"""Routes package initialization"""
from .main_routes import main_bp
from .api_routes import api_bp
from .agent_routes import agent_bp

__all__ = ['main_bp', 'api_bp', 'agent_bp']
