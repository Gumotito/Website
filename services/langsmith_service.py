"""
LangSmith Tracing Service

Optional LangSmith integration for agent tracing and monitoring.
"""
import os
from functools import wraps

# Try to import langsmith
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    # Create a dummy decorator if langsmith not available
    def traceable(name=None, **kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **inner_kwargs):
                return func(*args, **inner_kwargs)
            return wrapper
        return decorator


def setup_langsmith():
    """
    Setup LangSmith tracing if credentials are available
    
    Returns:
        True if LangSmith is configured and available
    """
    if not LANGSMITH_AVAILABLE:
        return False
    
    langchain_tracing = os.getenv('LANGCHAIN_TRACING_V2', 'false')
    langchain_api_key = os.getenv('LANGCHAIN_API_KEY')
    langchain_project = os.getenv('LANGCHAIN_PROJECT')
    
    if langchain_api_key and langchain_tracing.lower() == 'true':
        os.environ['LANGCHAIN_TRACING_V2'] = 'true'
        os.environ['LANGCHAIN_API_KEY'] = langchain_api_key
        os.environ['LANGCHAIN_PROJECT'] = langchain_project or 'website-agents'
        return True
    
    return False


# Export the traceable decorator
__all__ = ['traceable', 'setup_langsmith', 'LANGSMITH_AVAILABLE']
