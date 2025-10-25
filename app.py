from flask import Flask, render_template, jsonify, request
from datetime import datetime

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

@app.route('/agent/1/mail', methods=['POST'])
def mail_agent():
    data = request.json
    mail_text = data.get('mail', '')
    
    # Log received order
    order_logs['received'].append({
        'order': mail_text,
        'status': 'Received',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    # Parse order and check stock
    order_check = check_stock(mail_text)
    
    response = f"Order Received:\n\n{mail_text}\n\n--- Stock Verification ---\n{order_check}"
    
    return jsonify({'response': response})

@app.route('/agent/2/warehouse', methods=['POST'])
def warehouse_agent():
    global current_stock
    data = request.json
    stock_text = data.get('stock', '')
    
    # Parse stock format: Product A: 10units, Product B: 10units
    items = stock_text.split(',')
    for item in items:
        if ':' in item:
            product, qty_str = item.split(':')
            product = product.strip()
            # Extract number from qty_str (e.g., "10units" -> 10)
            qty = int(''.join(filter(str.isdigit, qty_str.strip())))
            current_stock[product] = qty
    
    stock_summary = "\n".join([f"{product}: {qty} units" for product, qty in current_stock.items()])
    response = f"Stock Updated:\n\n{stock_summary}"
    
    return jsonify({'response': response})

@app.route('/agent/3/approve', methods=['POST'])
def approve_order():
    data = request.json
    order = data.get('order', '')
    
    # Log approved order
    order_logs['approved'].append({
        'order': order,
        'status': 'Approved',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    # Add to awaiting payment
    order_logs['awaiting_payment'].append({
        'order': order,
        'status': 'Awaiting Payment',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    payment_order = f"Payment Order\n\n{order}\n\nTotal: Calculate based on order\n\nClick 'Pay Now' to proceed"
    
    response = f"Order Approved and Confirmed:\n\n{order}\n\nProcessing payment and shipping..."
    
    return jsonify({'response': response, 'payment_order': payment_order})

@app.route('/agent/4/fulfilled', methods=['POST'])
def fulfilled_delivery():
    global current_stock
    data = request.json
    order = data.get('order', '')
    
    # Add to awaiting delivery first
    order_logs['awaiting_delivery'].append({
        'order': order,
        'status': 'Awaiting Delivery',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    # Parse order and deduct from stock
    items = order.split(',')
    for item in items:
        item = item.strip()
        if item and ':' in item:
            prod_name, qty_str = item.split(':')
            prod_name = prod_name.strip()
            qty_ordered = int(''.join(filter(str.isdigit, qty_str.strip())))
            if prod_name in current_stock:
                current_stock[prod_name] -= qty_ordered
    
    # Generate updated stock
    updated_stock = "\n".join([f"{product}: {qty} units" for product, qty in current_stock.items()])
    
    confirmation = f"Order Delivered Successfully!\n\n{order}\n\nThank you for your purchase!"
    
    return jsonify({
        'confirmation': confirmation,
        'updated_stock': updated_stock
    })

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