"""
Utility Functions for Website Multi-Agent System

Helper functions for order parsing, stock checking, and JSON validation.
"""
import logging
from typing import List, Tuple, Dict
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)


def parse_order_items(order_text: str) -> List[Tuple[str, int]]:
    """
    Parse order text into list of (product, quantity) tuples
    
    Args:
        order_text: Text like "Product A: 5, Product B: 10"
        
    Returns:
        List of (product_name, quantity) tuples
    """
    items = []
    for item in order_text.split(','):
        item = item.strip()
        if item and ':' in item:
            try:
                prod_name, qty_str = item.split(':', 1)
                prod_name = prod_name.strip()
                qty = int(''.join(filter(str.isdigit, qty_str.strip())))
                if qty > 0:
                    items.append((prod_name, qty))
            except (ValueError, AttributeError) as e:
                logger.warning(f'Failed to parse item "{item}": {e}')
    return items


def check_stock_text(order_text: str, stock_dict: Dict[str, int]) -> str:
    """
    Generate stock availability text report for an order
    
    Args:
        order_text: Order text to check
        stock_dict: Current stock dictionary
        
    Returns:
        Formatted stock check report string
    """
    result = "Stock Check:\n"
    items = parse_order_items(order_text)
    
    for prod_name, qty_needed in items:
        qty_available = stock_dict.get(prod_name, 0)
        is_available = qty_available >= qty_needed
        status = "✓ Available" if is_available else "✗ Insufficient"
        result += f"{prod_name}: Need {qty_needed}, Have {qty_available} {status}\n"
    
    if not items:
        result += "No valid items found in order\n"
    
    return result


def validate_json(*required_fields):
    """
    Decorator to validate JSON request has required fields
    
    Usage:
        @validate_json('action', 'data')
        def my_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Invalid JSON'}), 400
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({'error': f'{field} is required'}), 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator
