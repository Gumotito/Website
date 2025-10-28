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
import pandas as pd
import time
from datetime import datetime as dt

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
# Use absolute path for stock file to avoid working directory issues
app.config['STOCK_FILE'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock_data.xlsx')
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
last_excel_modified_time = 0
monitoring_active = False

def save_stock():
    """Thread-safe stock persistence"""
    with stock_lock:
        try:
            stock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock.json')
            with open(stock_file, 'w') as f:
                json.dump(current_stock, f)
        except Exception as e:
            app.logger.error(f'Error saving stock: {e}')

def load_stock():
    """Load stock with thread safety"""
    global current_stock
    with stock_lock:
        try:
            stock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock.json')
            with open(stock_file, 'r') as f:
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

# Excel/API Integration Functions
def track_stock_changes(old_stock: Dict[str, int], new_stock: Dict[str, int]) -> Dict[str, Any]:
    """Compare old and new stock to track changes"""
    changes = {
        'added': {},
        'removed': {},
        'increased': {},
        'decreased': {},
        'unchanged': {}
    }
    
    all_products = set(old_stock.keys()) | set(new_stock.keys())
    
    for product in all_products:
        old_qty = old_stock.get(product, 0)
        new_qty = new_stock.get(product, 0)
        
        if product not in old_stock:
            changes['added'][product] = new_qty
        elif product not in new_stock:
            changes['removed'][product] = old_qty
        elif new_qty > old_qty:
            changes['increased'][product] = {'old': old_qty, 'new': new_qty, 'change': new_qty - old_qty}
        elif new_qty < old_qty:
            changes['decreased'][product] = {'old': old_qty, 'new': new_qty, 'change': old_qty - new_qty}
        else:
            changes['unchanged'][product] = new_qty
    
    return changes

def read_stock_from_excel(filepath: str) -> Tuple[bool, str, Dict[str, int]]:
    """Read stock data from Excel file"""
    try:
        if not os.path.exists(filepath):
            return False, f"Excel file not found: {filepath}", {}
        
        # Try reading as Excel first
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath, engine='openpyxl')
        
        # Validate required columns
        required_cols = {'Product', 'Quantity'}
        if not required_cols.issubset(df.columns):
            return False, f"Missing required columns. Need: {required_cols}", {}
        
        # Parse stock data
        stock_data = {}
        for _, row in df.iterrows():
            product = str(row['Product']).strip()
            try:
                quantity = int(row['Quantity'])
                if quantity >= 0:
                    stock_data[product] = quantity
            except (ValueError, TypeError) as e:
                app.logger.warning(f"Skipping invalid row for {product}: {e}")
                continue
        
        return True, "Successfully read Excel file", stock_data
    
    except Exception as e:
        app.logger.error(f"Error reading Excel file: {e}")
        return False, f"Error reading file: {str(e)}", {}

def apply_stock_changes(new_stock_data: Dict[str, int]) -> Tuple[Dict[str, Any], int]:
    """Apply new stock data and track changes"""
    with stock_lock:
        # Capture old state
        old_stock = current_stock.copy()
        
        # Track changes
        changes = track_stock_changes(old_stock, new_stock_data)
        
        # Apply new stock
        current_stock.clear()
        current_stock.update(new_stock_data)
        
        # Log all changes to database
        change_count = 0
        for product, qty in changes['added'].items():
            log_stock_change(product, qty, qty, 'excel_added')
            change_count += 1
        
        for product, old_qty in changes['removed'].items():
            log_stock_change(product, -old_qty, 0, 'excel_removed')
            change_count += 1
        
        for product, change_info in changes['increased'].items():
            log_stock_change(product, change_info['change'], change_info['new'], 'excel_increased')
            change_count += 1
        
        for product, change_info in changes['decreased'].items():
            log_stock_change(product, -change_info['change'], change_info['new'], 'excel_decreased')
            change_count += 1
        
        # Save to JSON
        save_stock()
        
        return changes, change_count

def update_excel_file(stock_data: Dict[str, int]) -> bool:
    """Write current stock back to Excel file"""
    try:
        excel_path = app.config['STOCK_FILE']
        
        # Create DataFrame from current stock
        df = pd.DataFrame([
            {'Product': product, 'Quantity': qty, 'Unit': 'units', 
             'Supplier': '', 'Last_Updated': dt.now().strftime('%Y-%m-%d')}
            for product, qty in stock_data.items()
        ])
        
        # Write to Excel
        df.to_excel(excel_path, index=False, engine='openpyxl')
        app.logger.info(f'Updated Excel file: {excel_path}')
        
        # Update modification time tracking to prevent re-read
        global last_excel_modified_time
        last_excel_modified_time = os.path.getmtime(excel_path)
        
        return True
    except Exception as e:
        app.logger.error(f'Error updating Excel file: {e}')
        return False

def monitor_excel_file():
    """Background thread to monitor Excel file for changes"""
    global last_excel_modified_time, monitoring_active
    
    monitoring_active = True
    excel_path = app.config['STOCK_FILE']
    
    app.logger.info(f'Starting Excel file monitor for: {excel_path}')
    
    while monitoring_active:
        try:
            if os.path.exists(excel_path):
                current_mtime = os.path.getmtime(excel_path)
                
                # Check if file was modified
                if current_mtime != last_excel_modified_time:
                    if last_excel_modified_time > 0:  # Skip first check on startup
                        app.logger.info(f'Excel file modified, auto-syncing stock...')
                        
                        success, message, new_stock_data = read_stock_from_excel(excel_path)
                        
                        if success and new_stock_data:
                            changes, change_count = apply_stock_changes(new_stock_data)
                            app.logger.info(f'Auto-sync complete: {change_count} changes detected')
                    
                    last_excel_modified_time = current_mtime
            
            time.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            app.logger.error(f'Error in Excel monitor: {e}')
            time.sleep(10)  # Wait longer on error

def start_excel_monitor():
    """Start the Excel monitoring thread"""
    monitor_thread = threading.Thread(target=monitor_excel_file, daemon=True)
    monitor_thread.start()
    app.logger.info('Excel file monitoring started')

def fetch_stock_from_api(api_url: str, api_key: Optional[str] = None) -> Tuple[bool, str, int]:
    """Fetch stock data from external API"""
    try:
        import requests
        
        headers = {}
        if api_key:
            headers['Authorization'] = f"Bearer {api_key}"
        
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Expect format: [{"product": "Name", "quantity": 10}, ...]
        # or {"products": [{"product": "Name", "quantity": 10}]}
        if isinstance(data, dict) and 'products' in data:
            data = data['products']
        
        if not isinstance(data, list):
            return False, "API response must be a list of products", 0
        
        updated_count = 0
        with stock_lock:
            for item in data:
                if 'product' in item and 'quantity' in item:
                    product = str(item['product']).strip()
                    try:
                        quantity = int(item['quantity'])
                        if quantity >= 0:
                            old_qty = current_stock.get(product, 0)
                            current_stock[product] = quantity
                            log_stock_change(product, quantity - old_qty, quantity, 'api_import')
                            updated_count += 1
                    except (ValueError, TypeError):
                        continue
            
            save_stock()
        
        return True, f"Successfully imported {updated_count} products from API", updated_count
    
    except requests.exceptions.RequestException as e:
        app.logger.error(f"API request failed: {e}")
        return False, f"API request failed: {str(e)}", 0
    except Exception as e:
        app.logger.error(f"Error fetching from API: {e}")
        return False, f"Error: {str(e)}", 0

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
    
    # Update Excel file with current stock after successful delivery
    with stock_lock:
        excel_updated = update_excel_file(current_stock.copy())
    if not excel_updated:
        app.logger.warning('Order fulfilled but Excel update failed')
    
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

# Start Excel monitoring thread
start_excel_monitor()

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
def warehouse_agent():
    """Agent 2: Read stock from Excel file and track changes"""
    try:
        data = request.json or {}
        
        # Option 1: Read from configured Excel file
        if data.get('action') == 'read_excel' or not data:
            excel_path = app.config['STOCK_FILE']
            
            success, message, new_stock_data = read_stock_from_excel(excel_path)
            
            if not success:
                return jsonify({'error': message}), 400
            
            if not new_stock_data:
                return jsonify({'error': 'No valid stock data found in Excel'}), 400
            
            # Apply changes and track them
            changes, change_count = apply_stock_changes(new_stock_data)
            
            # Format change summary
            change_summary = []
            if changes['added']:
                change_summary.append(f"✅ Added {len(changes['added'])} new products")
                for prod, qty in list(changes['added'].items())[:5]:
                    change_summary.append(f"   + {prod}: {qty} units")
                if len(changes['added']) > 5:
                    change_summary.append(f"   ... and {len(changes['added']) - 5} more")
            
            if changes['increased']:
                change_summary.append(f"📈 Increased {len(changes['increased'])} products")
                for prod, info in list(changes['increased'].items())[:5]:
                    change_summary.append(f"   ↑ {prod}: {info['old']} → {info['new']} (+{info['change']})")
                if len(changes['increased']) > 5:
                    change_summary.append(f"   ... and {len(changes['increased']) - 5} more")
            
            if changes['decreased']:
                change_summary.append(f"📉 Decreased {len(changes['decreased'])} products")
                for prod, info in list(changes['decreased'].items())[:5]:
                    change_summary.append(f"   ↓ {prod}: {info['old']} → {info['new']} (-{info['change']})")
                if len(changes['decreased']) > 5:
                    change_summary.append(f"   ... and {len(changes['decreased']) - 5} more")
            
            if changes['removed']:
                change_summary.append(f"❌ Removed {len(changes['removed'])} products")
                for prod in list(changes['removed'].keys())[:5]:
                    change_summary.append(f"   - {prod}")
                if len(changes['removed']) > 5:
                    change_summary.append(f"   ... and {len(changes['removed']) - 5} more")
            
            if changes['unchanged']:
                change_summary.append(f"➡️  Unchanged: {len(changes['unchanged'])} products")
            
            with stock_lock:
                stock_summary = "\n".join([f"{product}: {qty} units" 
                                          for product, qty in sorted(current_stock.items())])
            
            response_text = f"""Stock Updated from Excel: {excel_path}

Changes Detected ({change_count} total):
{chr(10).join(change_summary)}

Current Stock ({len(current_stock)} products):
{stock_summary}"""
            
            return jsonify({
                'response': response_text,
                'method': 'excel_monitor',
                'changes': changes,
                'change_count': change_count,
                'total_products': len(current_stock)
            })
        
        # Option 2: Manual text entry (backward compatibility)
        elif 'stock' in data:
            stock_text = data.get('stock', '')
            
            updated_items = warehouse_agent_traced(stock_text)
            
            if not updated_items:
                return jsonify({'error': 'No valid stock items to update'}), 400
            
            with stock_lock:
                stock_summary = "\n".join([f"{product}: {qty} units" 
                                          for product, qty in current_stock.items()])
            
            return jsonify({
                'response': f"Stock Updated Manually:\n\n{stock_summary}",
                'method': 'manual',
                'count': len(updated_items)
            })
        
        # Option 3: API integration
        elif 'api_url' in data:
            api_url = data.get('api_url')
            api_key = data.get('api_key')
            
            success, message, count = fetch_stock_from_api(api_url, api_key)
            
            if not success:
                return jsonify({'error': message}), 400
            
            with stock_lock:
                stock_summary = "\n".join([f"{product}: {qty} units" 
                                          for product, qty in current_stock.items()])
            
            return jsonify({
                'response': f"Stock Updated from API:\n\n{message}\n\n{stock_summary}",
                'method': 'api',
                'count': count
            })
        
        else:
            return jsonify({'error': 'Invalid request. Use action=read_excel, provide stock text, or api_url'}), 400
            
    except Exception as e:
        app.logger.error(f'Error in warehouse_agent: {e}')
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

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