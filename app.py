from flask import Flask, render_template, jsonify, request
from datetime import datetime
from langsmith import traceable
import os
from dotenv import load_dotenv

load_dotenv()

# Load from environment variables only - NO HARDCODED SECRETS
LANGCHAIN_TRACING = os.getenv('LANGCHAIN_TRACING_V2', 'false')
LANGCHAIN_API_KEY = os.getenv('LANGCHAIN_API_KEY')
LANGCHAIN_PROJECT = os.getenv('LANGCHAIN_PROJECT')

# Only set if API key exists
if LANGCHAIN_API_KEY:
    os.environ['LANGCHAIN_TRACING_V2'] = LANGCHAIN_TRACING
    os.environ['LANGCHAIN_API_KEY'] = LANGCHAIN_API_KEY
    os.environ['LANGCHAIN_PROJECT'] = LANGCHAIN_PROJECT or 'website-agents'

app = Flask(__name__)

# Store current stock
current_stock = {}

# Store logs
order_logs = {
    'received': [],
    'approved': [],
    'awaiting_payment': [],
    'awaiting_delivery': [],
    'delivered': []
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/api/logs')
def get_logs():
    return jsonify(order_logs)

@app.route('/agent/<int:agent_id>')
def get_agent(agent_id):
    agents_data = {
        1: {'name': 'Agent 1', 'description': 'Mail Interface'},
        2: {'name': 'Agent 2', 'description': 'Warehouse'},
        3: {'name': 'Agent 3', 'description': 'Area 3 content'},
        4: {'name': 'Agent 4', 'description': 'Area 4 content'}
    }
    return jsonify(agents_data.get(agent_id, {}))

@traceable(name="Agent 1 - Mail Processing")
def mail_agent_traced(mail_text):
    """Agent 1: Process incoming mail orders"""
    order_logs['received'].append({
        'order': mail_text,
        'status': 'Received',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    order_check = check_stock(mail_text)
    return f"Order Received:\n\n{mail_text}\n\n--- Stock Verification ---\n{order_check}"

@traceable(name="Agent 2 - Stock Update")
def warehouse_agent_traced(stock_text):
    """Agent 2: Update warehouse stock"""
    items = stock_text.split(',')
    updated_items = []
    for item in items:
        if ':' in item:
            product, qty_str = item.split(':')
            product = product.strip()
            qty = int(''.join(filter(str.isdigit, qty_str.strip())))
            current_stock[product] = qty
            updated_items.append(f"{product}: {qty}")
    return "\n".join(updated_items)

@traceable(name="Agent 3 - Order Approval")
def approve_order_traced(order):
    """Agent 3: Approve orders"""
    order_logs['approved'].append({
        'order': order,
        'status': 'Approved',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    order_logs['awaiting_payment'].append({
        'order': order,
        'status': 'Awaiting Payment',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    return f"Order Approved: {order}"

@traceable(name="Agent 4 - Delivery Fulfillment")
def fulfilled_delivery_traced(order):
    """Agent 4: Fulfill and deliver orders"""
    order_logs['awaiting_delivery'].append({
        'order': order,
        'status': 'Awaiting Delivery',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    items = order.split(',')
    for item in items:
        item = item.strip()
        if item and ':' in item:
            prod_name, qty_str = item.split(':')
            prod_name = prod_name.strip()
            qty_ordered = int(''.join(filter(str.isdigit, qty_str.strip())))
            if prod_name in current_stock:
                current_stock[prod_name] -= qty_ordered
    return f"Order Fulfilled: {order}"

@traceable(name="Agent 5 - Flow Oversight")
def oversee_flow():
    """Agent 5: Monitor and analyze workflow performance"""
    metrics = {
        'total_received': len(order_logs['received']),
        'total_approved': len(order_logs['approved']),
        'total_paid': len(order_logs['awaiting_payment']) + len(order_logs['awaiting_delivery']) + len(order_logs['delivered']),
        'total_delivered': len(order_logs['delivered']),
        'pending_approval': len(order_logs['received']) - len(order_logs['approved']),
        'pending_payment': len(order_logs['awaiting_payment']),
        'pending_delivery': len(order_logs['awaiting_delivery']),
        'current_stock_value': sum(current_stock.values()),
        'low_stock_items': [item for item, qty in current_stock.items() if qty < 5]
    }
    return metrics

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
    if metrics['total_delivered'] > 0:
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

@app.route('/agent/1/mail', methods=['POST'])
def mail_agent():
    data = request.json
    mail_text = data.get('mail', '')
    response = mail_agent_traced(mail_text)
    return jsonify({'response': response})

@app.route('/agent/2/warehouse', methods=['POST'])
def warehouse_agent():
    data = request.json
    stock_text = data.get('stock', '')
    warehouse_agent_traced(stock_text)
    stock_summary = "\n".join([f"{product}: {qty} units" for product, qty in current_stock.items()])
    return jsonify({'response': f"Stock Updated:\n\n{stock_summary}"})

@app.route('/agent/3/approve', methods=['POST'])
def approve_order():
    data = request.json
    order = data.get('order', '')
    approve_order_traced(order)
    payment_order = f"Payment Order\n\n{order}\n\nClick 'Pay Now' to proceed"
    return jsonify({'response': f"Order Approved: {order}", 'payment_order': payment_order})

@app.route('/agent/4/fulfilled', methods=['POST'])
def fulfilled_delivery():
    data = request.json
    order = data.get('order', '')
    fulfilled_delivery_traced(order)
    updated_stock = "\n".join([f"{product}: {qty} units" for product, qty in current_stock.items()])
    confirmation = f"Order Delivered Successfully!\n\n{order}\n\nThank you!"
    return jsonify({'confirmation': confirmation, 'updated_stock': updated_stock})

@app.route('/agent/4/delivery-complete', methods=['POST'])
def delivery_complete():
    data = request.json
    order = data.get('order', '')
    
    # Remove from awaiting delivery
    order_logs['awaiting_delivery'] = [log for log in order_logs['awaiting_delivery'] if log['order'] != order]
    
    # Add to delivered
    order_logs['delivered'].append({
        'order': order,
        'status': 'Delivered',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    return jsonify({'success': True})

def check_stock(products):
    result = "Stock Check:\n"
    # Parse comma-separated format: Product A:5, Product B:10
    items = products.split(',')
    for item in items:
        item = item.strip()
        if item and ':' in item:
            prod_name, qty_str = item.split(':')
            prod_name = prod_name.strip()
            qty_needed = int(''.join(filter(str.isdigit, qty_str.strip())))
            qty_available = current_stock.get(prod_name, 0)
            status = "✓ Available" if qty_available >= qty_needed else "✗ Insufficient"
            result += f"{prod_name}: Need {qty_needed}, Have {qty_available} {status}\n"
    return result

if __name__ == '__main__':
    app.run(debug=True)