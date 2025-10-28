"""
API Routes for Website

RESTful API endpoints for logs and metrics.
"""
from flask import Blueprint, jsonify, request
from database import get_all_orders_paginated, get_stock_history

api_bp = Blueprint('api', __name__)


@api_bp.route('/logs')
def get_logs():
    """Get logs with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    result = get_all_orders_paginated(page, per_page)
    return jsonify(result)


@api_bp.route('/stock-history')
def stock_history():
    """Get stock change history"""
    limit = request.args.get('limit', 100, type=int)
    history = get_stock_history(limit)
    return jsonify({'history': history})
