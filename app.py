from flask import Flask, render_template, jsonify, request
from datetime import datetime
import os
from dotenv import load_dotenv
import json
import sqlite3
from flask_cors import CORS
from functools import wraps, lru_cache
import threading
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Tuple, Optional, Any
from pydantic import BaseModel, field_validator, Field

load_dotenv()

# Try to import langsmith, but make it optional
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    # Create a dummy decorator if langsmith is not available
    def traceable(name=None):
        def decorator(func):
            return func
        return decorator

# Load from environment variables only
LANGCHAIN_TRACING = os.getenv('LANGCHAIN_TRACING_V2', 'false')
LANGCHAIN_API_KEY = os.getenv('LANGCHAIN_API_KEY')
LANGCHAIN_PROJECT = os.getenv('LANGCHAIN_PROJECT')

if LANGCHAIN_API_KEY and LANGSMITH_AVAILABLE:
    os.environ['LANGCHAIN_TRACING_V2'] = LANGCHAIN_TRACING
    os.environ['LANGCHAIN_API_KEY'] = LANGCHAIN_API_KEY
    os.environ['LANGCHAIN_PROJECT'] = LANGCHAIN_PROJECT or 'website-agents'

app = Flask(__name__)
CORS(app)

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')

handler = RotatingFileHandler('logs/website.log', maxBytes=10000000, backupCount=3)
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Website startup')

# Initialize Limiter
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

# Pydantic Models for Validation
class OrderItem(BaseModel):
    product: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(..., gt=0)
    
    @field_validator('product')
    @classmethod
    def product_alphanumeric(cls, v):
        if not v.replace(' ', '').replace('-', '').replace('_', '').isalnum():
            raise ValueError('Product name must be alphanumeric')
        return v.strip()

class StockUpdate(BaseModel):
    items: List[OrderItem]

class Order(BaseModel):
    order_text: str = Field(..., min_length=3, max_length=1000)

# Add validation decorator
def validate_json(*required_fields):
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

# Thread-safe stock management
stock_lock = threading.Lock()
current_stock = {}

# Thread-safe stock management
stock_lock = threading.Lock()
current_stock = {}

def save_stock():
    """Thread-safe stock persistence"""
    with stock_lock:
        try:
            with open('stock.json', 'w') as f:
                json.dump(current_stock, f)
        except Exception as e:
            app.logger.error(f'Error saving stock: {e}')

def load_stock():
    """Load stock with thread safety"""
    global current_stock
    with stock_lock:
        try:
            with open('stock.json', 'r') as f:
                current_stock = json.load(f)
                app.logger.info(f'Loaded stock: {len(current_stock)} items')
        except FileNotFoundError:
            current_stock = {}
            app.logger.info('No existing stock file, starting fresh')
        except Exception as e:
            app.logger.error(f'Error loading stock: {e}')
            current_stock = {}

def update_stock_item(product: str, quantity: int) -> bool:
    """Thread-safe stock update"""
    with stock_lock:
        current_stock[product] = quantity
        save_stock()
        return True

def deduct_stock(product: str, quantity: int) -> Tuple[bool, str]:
    """Thread-safe stock deduction with validation"""
    with stock_lock:
        if product not in current_stock:
            return False, f'Product {product} not found in stock'
        if current_stock[product] < quantity:
            return False, f'Insufficient stock for {product}: need {quantity}, have {current_stock[product]}'
        current_stock[product] -= quantity
        save_stock()
        return True, 'Stock deducted successfully'

def check_stock_availability(product: str, quantity: int) -> Tuple[bool, int]:
    """Thread-safe stock availability check"""
    with stock_lock:
        available = current_stock.get(product, 0)
        return available >= quantity, available

# Database operations
def get_db_connection():
    """Create thread-safe database connection"""
    conn = sqlite3.connect('orders.db', check_same_thread=False)
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
        app.logger.info('Database initialized successfully')
    except Exception as e:
        app.logger.error(f'Error initializing database: {e}')
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
        app.logger.info(f'Saved order {order_id} with status {status}')
        return order_id
    except Exception as e:
        app.logger.error(f'Error saving order: {e}')
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
        app.logger.error(f'Error updating order status: {e}')
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
        app.logger.error(f'Error fetching orders: {e}')
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
        app.logger.error(f'Error fetching orders: {e}')
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
        app.logger.error(f'Error logging stock change: {e}')
    finally:
        conn.close()

# Utility functions
def parse_order_items(order_text: str) -> List[Tuple[str, int]]:
    """Parse order text into list of (product, quantity) tuples"""
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
                app.logger.warning(f'Failed to parse item "{item}": {e}')
    return items

def check_stock(order_text: str) -> str:
    """Check stock availability for order"""
    result = "Stock Check:\n"
    items = parse_order_items(order_text)
    
    for prod_name, qty_needed in items:
        is_available, qty_available = check_stock_availability(prod_name, qty_needed)
        status = "✓ Available" if is_available else "✗ Insufficient"
        result += f"{prod_name}: Need {qty_needed}, Have {qty_available} {status}\n"
    
    if not items:
        result += "No valid items found in order\n"
    
    return result

@traceable(name="Agent 1 - Mail Processing")
def mail_agent_traced(mail_text: str) -> Tuple[str, int]:
    """Agent 1: Process incoming mail orders"""
    # Save to database
    order_id = save_order_to_db(mail_text, 'received', agent=1)
    
    # Check stock
    order_check = check_stock(mail_text)
    
    return f"Order #{order_id} Received:\n\n{mail_text}\n\n--- Stock Verification ---\n{order_check}", order_id

@traceable(name="Agent 2 - Stock Update")
def warehouse_agent_traced(stock_text: str) -> List[str]:
    """Agent 2: Update warehouse stock"""
    items = stock_text.split(',')
    updated_items = []
    
    for item in items:
        if ':' in item:
            product, qty_str = item.split(':')
            product = product.strip()
            try:
                qty = int(''.join(filter(str.isdigit, qty_str.strip())))
                old_qty = current_stock.get(product, 0)
                update_stock_item(product, qty)
                log_stock_change(product, qty - old_qty, qty, 'manual_update')
                updated_items.append(f"{product}: {qty}")
            except ValueError as e:
                app.logger.error(f'Error parsing quantity for {product}: {e}')
                
    return updated_items

@traceable(name="Agent 3 - Order Approval")
def approve_order_traced(order_id: int, order: str) -> str:
    """Agent 3: Approve orders"""
    update_order_status(order_id, 'approved')
    save_order_to_db(order, 'awaiting_payment', agent=3)
    return f"Order #{order_id} Approved: {order}"

@traceable(name="Agent 4 - Delivery Fulfillment")
def fulfilled_delivery_traced(order: str) -> Tuple[bool, str]:
    """Agent 4: Fulfill and deliver orders"""
    save_order_to_db(order, 'awaiting_delivery', agent=4)
    
    items = order.split(',')
    failed_items = []
    
    for item in items:
        item = item.strip()
        if item and ':' in item:
            prod_name, qty_str = item.split(':')
            prod_name = prod_name.strip()
            try:
                qty_ordered = int(''.join(filter(str.isdigit, qty_str.strip())))
                success, message = deduct_stock(prod_name, qty_ordered)
                if not success:
                    failed_items.append(f"{prod_name}: {message}")
                else:
                    log_stock_change(prod_name, -qty_ordered, current_stock[prod_name], 'order_fulfillment')
            except ValueError:
                failed_items.append(f"{prod_name}: Invalid quantity format")
    
    if failed_items:
        return False, "Fulfillment failed:\n" + "\n".join(failed_items)
    
    return True, f"Order Fulfilled: {order}"

@traceable(name="Agent 5 - Flow Oversight")
def oversee_flow() -> Dict[str, Any]:
    """Agent 5: Monitor and analyze workflow performance"""
    conn = get_db_connection()
    try:
        # Count orders by status
        received = conn.execute("SELECT COUNT(*) FROM orders WHERE status='received'").fetchone()[0]
        approved = conn.execute("SELECT COUNT(*) FROM orders WHERE status='approved'").fetchone()[0]
        awaiting_payment = conn.execute("SELECT COUNT(*) FROM orders WHERE status='awaiting_payment'").fetchone()[0]
        awaiting_delivery = conn.execute("SELECT COUNT(*) FROM orders WHERE status='awaiting_delivery'").fetchone()[0]
        delivered = conn.execute("SELECT COUNT(*) FROM orders WHERE status='delivered'").fetchone()[0]
        
        with stock_lock:
            stock_value = sum(current_stock.values())
            low_stock_items = [item for item, qty in current_stock.items() if qty < 5]
        
        metrics = {
            'total_received': received,
            'total_approved': approved,
            'total_paid': awaiting_payment + awaiting_delivery + delivered,
            'total_delivered': delivered,
            'pending_approval': received - approved,
            'pending_payment': awaiting_payment,
            'pending_delivery': awaiting_delivery,
            'current_stock_value': stock_value,
            'low_stock_items': low_stock_items
        }
        return metrics
    except Exception as e:
        app.logger.error(f'Error in oversee_flow: {e}')
        return {}
    finally:
        conn.close()

def generate_insights():
    """Generate improvement recommendations"""
    metrics = oversee_flow()
    insights = []
    
    # Check for bottlenecks
    if metrics['pending_approval'] > 2:
        insights.append("⚠️  Multiple orders awaiting approval - consider faster approval process")
    
    if metrics['pending_payment'] > 3:
        insights.append("⚠️  Multiple orders awaiting payment - send payment reminders")
    
    if metrics['pending_delivery'] > 2:
        insights.append("⚠️  Delivery backlog detected - allocate more resources")
    
    # Stock warnings
    if metrics['low_stock_items']:
        insights.append(f"📦 Low stock items: {', '.join(metrics['low_stock_items'])} - Reorder soon")
    
    # Performance insights
    if metrics['total_received'] > 0 and metrics['total_delivered'] > 0:
        delivery_rate = (metrics['total_delivered'] / metrics['total_received']) * 100
        insights.append(f"✅ Delivery rate: {delivery_rate:.1f}%")
    
    return insights

@app.route('/agent/5/oversight', methods=['GET'])
def get_oversight():
    """Get workflow metrics and insights"""
    metrics = oversee_flow()
    insights = generate_insights()
    
    return jsonify({
        'metrics': metrics,
        'insights': insights,
        'status': 'healthy' if not insights else 'warning'
    })

@app.route('/agent/5/recommendations', methods=['GET'])
def get_recommendations():
    """Get AI-powered improvement recommendations"""
    metrics = oversee_flow()
    recommendations = []
    
    # Efficiency recommendations
    if metrics['total_approved'] > 0:
        approval_rate = (metrics['total_approved'] / metrics['total_received']) * 100
        if approval_rate < 80:
            recommendations.append({
                'category': 'Approval Process',
                'improvement': 'Slow approval rate - Consider automated approval for standard orders',
                'priority': 'high'
            })
    
    # Payment recommendations
    if metrics['pending_payment'] > 0:
        recommendations.append({
            'category': 'Payment',
            'improvement': 'Implement payment reminders and multiple payment methods',
            'priority': 'high' if metrics['pending_payment'] > 2 else 'medium'
        })
    
    # Delivery recommendations
    if metrics['pending_delivery'] > 1:
        recommendations.append({
            'category': 'Delivery',
            'improvement': 'Consider partnering with multiple delivery providers',
            'priority': 'high' if metrics['pending_delivery'] > 3 else 'medium'
        })
    
    # Stock recommendations
    if metrics['low_stock_items']:
        recommendations.append({
            'category': 'Inventory',
            'improvement': f"Implement automated reordering for low-stock items",
            'priority': 'high'
        })
    else:
        recommendations.append({
            'category': 'Inventory',
            'improvement': 'Stock levels are healthy - Continue current inventory management',
            'priority': 'low'
        })
    
    # Capacity recommendations
    if metrics['total_delivered'] > 10:
        recommendations.append({
            'category': 'Capacity',
            'improvement': 'Scale up operations - Consider hiring additional staff',
            'priority': 'medium'
        })
    
    return jsonify({'recommendations': recommendations})

# Load stock on startup BEFORE routes
load_stock()
init_db()

# NOW define routes AFTER everything is initialized
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/api/logs')
def get_logs():
    """Get logs with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    result = get_all_orders_paginated(page, per_page)
    return jsonify(result)

@app.route('/agent/<int:agent_id>')
def get_agent(agent_id):
    agents_data = {
        1: {'name': 'Agent 1', 'description': 'Mail Interface'},
        2: {'name': 'Agent 2', 'description': 'Warehouse'},
        3: {'name': 'Agent 3', 'description': 'Area 3 content'},
        4: {'name': 'Agent 4', 'description': 'Area 4 content'}
    }
    return jsonify(agents_data.get(agent_id, {}))

@app.route('/agent/1/mail', methods=['POST'])
@limiter.limit("10 per minute")
@validate_json('mail')
def mail_agent():
    """Agent 1: Process incoming mail orders"""
    try:
        data = request.json
        mail_text = data.get('mail', '').strip()
        
        if len(mail_text) < 3:
            return jsonify({'error': 'Mail text too short'}), 400
        
        response, order_id = mail_agent_traced(mail_text)
        return jsonify({'response': response, 'order_id': order_id})
    except Exception as e:
        app.logger.error(f'Error in mail_agent: {e}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/agent/2/warehouse', methods=['POST'])
@limiter.limit("20 per minute")
@validate_json('stock')
def warehouse_agent():
    """Agent 2: Update warehouse stock"""
    try:
        data = request.json
        stock_text = data.get('stock', '')
        
        updated_items = warehouse_agent_traced(stock_text)
        
        if not updated_items:
            return jsonify({'error': 'No valid stock items to update'}), 400
        
        stock_summary = "\n".join([f"{product}: {qty} units" 
                                   for product, qty in current_stock.items()])
        return jsonify({'response': f"Stock Updated:\n\n{stock_summary}"})
    except ValueError as e:
        app.logger.error(f'Error in warehouse_agent: {e}')
        return jsonify({'error': f'Invalid stock format: {str(e)}'}), 400
    except Exception as e:
        app.logger.error(f'Error in warehouse_agent: {e}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/agent/3/approve', methods=['POST'])
@limiter.limit("15 per minute")
def approve_order():
    """Agent 3: Approve orders"""
    try:
        data = request.json
        order = data.get('order', '')
        order_id = data.get('order_id', 0)
        
        if not order:
            return jsonify({'error': 'Order text is required'}), 400
        
        response = approve_order_traced(order_id, order)
        payment_order = f"Payment Order\n\n{order}\n\nClick 'Pay Now' to proceed"
        return jsonify({'response': response, 'payment_order': payment_order, 'order_id': order_id})
    except Exception as e:
        app.logger.error(f'Error in approve_order: {e}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/agent/4/fulfilled', methods=['POST'])
@limiter.limit("10 per minute")
def fulfilled_delivery():
    """Agent 4: Fulfill and deliver orders"""
    try:
        data = request.json
        order = data.get('order', '')
        
        if not order:
            return jsonify({'error': 'Order text is required'}), 400
        
        success, message = fulfilled_delivery_traced(order)
        
        if not success:
            return jsonify({'error': message}), 400
        
        with stock_lock:
            updated_stock = "\n".join([f"{product}: {qty} units" 
                                      for product, qty in current_stock.items()])
        
        confirmation = f"Order Delivered Successfully!\n\n{order}\n\nThank you!"
        return jsonify({'confirmation': confirmation, 'updated_stock': updated_stock})
    except Exception as e:
        app.logger.error(f'Error in fulfilled_delivery: {e}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/agent/4/delivery-complete', methods=['POST'])
def delivery_complete():
    """Mark order as delivered"""
    data = request.json
    order = data.get('order', '')
    order_id = data.get('order_id', 0)
    
    try:
        # Update order status to delivered
        if order_id:
            update_order_status(order_id, 'delivered')
        else:
            save_order_to_db(order, 'delivered', agent=4)
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f'Error marking delivery complete: {e}')
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)