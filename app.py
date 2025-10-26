from flask import Flask, render_template, jsonify, request
from datetime import datetime
from langsmith import traceable
import os

app = Flask(__name__)

# LangSmith setup
os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_PROJECT'] = 'website-agents'

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