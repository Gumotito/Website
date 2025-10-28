"""
Database Operations for Website Multi-Agent System

Handles all SQLite database operations including orders, order items, and stock history.
"""
import sqlite3
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)


def get_db_connection():
    """Create thread-safe database connection"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'orders.db')
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database with proper schema"""
    conn = get_db_connection()
    try:
        # Orders table with more fields
        conn.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_text TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            agent INTEGER,
            details TEXT
        )''')
        
        # Order items table for better tracking
        conn.execute('''CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )''')
        
        # Stock history for auditing
        conn.execute('''CREATE TABLE IF NOT EXISTS stock_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT NOT NULL,
            quantity_change INTEGER NOT NULL,
            new_quantity INTEGER NOT NULL,
            reason TEXT,
            timestamp TEXT NOT NULL
        )''')
        
        conn.commit()
        logger.info('Database initialized successfully')
    except Exception as e:
        logger.error(f'Error initializing database: {e}')
    finally:
        conn.close()


def save_order_to_db(order_text: str, status: str, agent: int, details: Optional[Dict] = None) -> int:
    """Save order to database and return order ID"""
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            'INSERT INTO orders (order_text, status, timestamp, agent, details) VALUES (?, ?, ?, ?, ?)',
            (order_text, status, datetime.now().isoformat(), agent, json.dumps(details) if details else None)
        )
        order_id = cursor.lastrowid
        conn.commit()
        logger.info(f'Saved order {order_id} with status {status}')
        return order_id
    except Exception as e:
        logger.error(f'Error saving order: {e}')
        conn.rollback()
        return -1
    finally:
        conn.close()


def update_order_status(order_id: int, status: str) -> bool:
    """Update order status"""
    conn = get_db_connection()
    try:
        conn.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f'Error updating order status: {e}')
        return False
    finally:
        conn.close()


def get_orders_by_status(status: str, limit: int = 100) -> List[Dict]:
    """Get orders by status with pagination"""
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            'SELECT * FROM orders WHERE status = ? ORDER BY timestamp DESC LIMIT ?',
            (status, limit)
        )
        orders = [dict(row) for row in cursor.fetchall()]
        return orders
    except Exception as e:
        logger.error(f'Error fetching orders: {e}')
        return []
    finally:
        conn.close()


def get_all_orders_paginated(page: int = 1, per_page: int = 50) -> Dict:
    """Get all orders with pagination"""
    conn = get_db_connection()
    try:
        offset = (page - 1) * per_page
        cursor = conn.execute(
            'SELECT * FROM orders ORDER BY timestamp DESC LIMIT ? OFFSET ?',
            (per_page, offset)
        )
        orders = [dict(row) for row in cursor.fetchall()]
        
        # Get total count
        total = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
        
        return {
            'orders': orders,
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page
        }
    except Exception as e:
        logger.error(f'Error fetching orders: {e}')
        return {'orders': [], 'page': 1, 'per_page': per_page, 'total': 0, 'pages': 0}
    finally:
        conn.close()


def log_stock_change(product: str, quantity_change: int, new_quantity: int, reason: str):
    """Log stock changes for auditing"""
    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO stock_history (product, quantity_change, new_quantity, reason, timestamp) VALUES (?, ?, ?, ?, ?)',
            (product, quantity_change, new_quantity, reason, datetime.now().isoformat())
        )
        conn.commit()
    except Exception as e:
        logger.error(f'Error logging stock change: {e}')
    finally:
        conn.close()


def get_stock_history(limit: int = 100) -> List[Dict]:
    """Get stock change history"""
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            'SELECT * FROM stock_history ORDER BY timestamp DESC LIMIT ?',
            (limit,)
        )
        history = [dict(row) for row in cursor.fetchall()]
        return history
    except Exception as e:
        logger.error(f'Error fetching stock history: {e}')
        return []
    finally:
        conn.close()
