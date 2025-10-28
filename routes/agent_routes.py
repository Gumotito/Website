"""
Agent Routes for Website

All agent endpoints (1-5) with rate limiting and validation.
"""
from flask import Blueprint, jsonify, request, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from utils import validate_json
from agents import (
    process_mail, update_stock_manual, fetch_from_api, sync_excel,
    approve_order as approve_order_agent, fulfill_delivery,
    oversee_flow, generate_insights
)
from database import save_order_to_db, update_order_status

agent_bp = Blueprint('agent', __name__)

# Note: Limiter will be registered in app.py
# Individual route limits are applied in app.py via @limiter.limit()


@agent_bp.route('/<int:agent_id>')
def get_agent(agent_id):
    """Get agent info"""
    agents_data = {
        1: {"name": "Mail Agent", "description": "Processes incoming orders"},
        2: {"name": "Warehouse Agent", "description": "Manages stock inventory"},
        3: {"name": "Approval Agent", "description": "Approves orders"},
        4: {"name": "Delivery Agent", "description": "Fulfills deliveries"},
        5: {"name": "Oversight Agent", "description": "Monitors workflow"}
    }
    
    agent = agents_data.get(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404
    
    return jsonify(agent)


@agent_bp.route('/1/mail', methods=['POST'])
@validate_json('mail')
def mail_agent():
    """Agent 1: Process incoming mail orders"""
    try:
        data = request.json
        mail_text = data.get('mail', '').strip()
        
        if len(mail_text) < 3:
            return jsonify({'error': 'Mail text too short'}), 400
        
        # Get stock service from app context
        stock_service = current_app.stock_service
        current_stock = stock_service.get_all()
        
        response, order_id = process_mail(mail_text, current_stock)
        return jsonify({'response': response, 'order_id': order_id})
    except Exception as e:
        current_app.logger.error(f'Error in mail_agent: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@agent_bp.route('/2/warehouse', methods=['POST'])
def warehouse_agent():
    """Agent 2: Warehouse operations (Excel sync, manual update, API import)"""
    try:
        current_app.logger.info('Agent 2 warehouse endpoint called')
        data = request.json or {}
        stock_service = current_app.stock_service
        excel_service = current_app.excel_service
        
        action = data.get('action', 'read_excel')
        current_app.logger.info(f'Action: {action}')
        
        # Option 1: Read from Excel file
        if action == 'read_excel' or not data:
            current_app.logger.info('Starting Excel sync...')
            result = sync_excel(excel_service)
            current_app.logger.info(f'Sync result: {result}')
            changes = result['changes']
            change_count = result['change_count']
            
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
            
            if changes['decreased']:
                change_summary.append(f"📉 Decreased {len(changes['decreased'])} products")
                for prod, info in list(changes['decreased'].items())[:5]:
                    change_summary.append(f"   ↓ {prod}: {info['old']} → {info['new']} (-{info['change']})")
            
            if changes['removed']:
                change_summary.append(f"❌ Removed {len(changes['removed'])} products")
            
            if changes['unchanged']:
                change_summary.append(f"➡️  Unchanged: {len(changes['unchanged'])} products")
            
            return jsonify({
                'message': f'Stock synchronized from Excel. {change_count} changes detected.',
                'changes': changes,
                'change_count': change_count,
                'change_summary': change_summary,
                'current_stock': stock_service.get_all()
            })
        
        # Option 2: Manual stock update
        elif action == 'manual_update':
            stock_text = data.get('stock', '').strip()
            if not stock_text:
                return jsonify({'error': 'Stock text is required'}), 400
            
            updated_items = update_stock_manual(stock_text, stock_service)
            return jsonify({
                'message': f'Updated {len(updated_items)} items',
                'updated_items': updated_items,
                'current_stock': stock_service.get_all()
            })
        
        # Option 3: Fetch from API
        elif action == 'fetch_api':
            api_url = data.get('api_url')
            api_key = data.get('api_key')
            
            if not api_url:
                return jsonify({'error': 'API URL is required'}), 400
            
            success, message, items_updated = fetch_from_api(api_url, stock_service, api_key)
            
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({
                'message': message,
                'items_updated': items_updated,
                'current_stock': stock_service.get_all()
            })
        
        else:
            return jsonify({'error': f'Unknown action: {action}'}), 400
    
    except Exception as e:
        current_app.logger.error(f'Error in warehouse_agent: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@agent_bp.route('/3/approve', methods=['POST'])
def approve_order():
    """Agent 3: Approve orders"""
    try:
        data = request.json
        order = data.get('order', '')
        order_id = data.get('order_id', 0)
        
        if not order:
            return jsonify({'error': 'Order text is required'}), 400
        
        response = approve_order_agent(order_id, order)
        payment_order = f"Payment Order\n\n{order}\n\nClick 'Pay Now' to proceed"
        return jsonify({
            'response': response,
            'payment_order': payment_order,
            'order_id': order_id
        })
    except Exception as e:
        current_app.logger.error(f'Error in approve_order: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@agent_bp.route('/4/fulfilled', methods=['POST'])
def fulfilled_delivery_route():
    """Agent 4: Fulfill and deliver orders"""
    try:
        data = request.json
        order = data.get('order', '')
        
        if not order:
            return jsonify({'error': 'Order text is required'}), 400
        
        stock_service = current_app.stock_service
        excel_service = current_app.excel_service
        
        success, message = fulfill_delivery(order, stock_service, excel_service)
        
        if not success:
            return jsonify({'error': message}), 400
        
        updated_stock = "\n".join([
            f"{product}: {qty} units"
            for product, qty in stock_service.get_all().items()
        ])
        
        confirmation = f"Order Delivered Successfully!\n\n{order}\n\nThank you!"
        return jsonify({
            'confirmation': confirmation,
            'updated_stock': updated_stock
        })
    except Exception as e:
        current_app.logger.error(f'Error in fulfilled_delivery: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@agent_bp.route('/4/delivery-complete', methods=['POST'])
def delivery_complete():
    """Mark order as delivered"""
    data = request.json
    order = data.get('order', '')
    order_id = data.get('order_id', 0)
    
    try:
        if order_id:
            update_order_status(order_id, 'delivered')
        else:
            save_order_to_db(order, 'delivered', agent=4)
        
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f'Error marking delivery complete: {e}')
        return jsonify({'error': str(e)}), 500


@agent_bp.route('/5/oversight', methods=['GET'])
def get_oversight():
    """Get workflow metrics and insights"""
    try:
        stock_service = current_app.stock_service
        metrics = oversee_flow(stock_service)
        insights = generate_insights(metrics)
        
        return jsonify({
            'metrics': metrics,
            'insights': insights,
            'status': 'healthy' if not insights else 'warning'
        })
    except Exception as e:
        current_app.logger.error(f'Error in get_oversight: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@agent_bp.route('/5/recommendations', methods=['GET'])
def get_recommendations():
    """Get AI-powered improvement recommendations"""
    try:
        stock_service = current_app.stock_service
        metrics = oversee_flow(stock_service)
        insights = generate_insights(metrics)
        
        return jsonify({
            'recommendations': insights,
            'metrics': metrics
        })
    except Exception as e:
        current_app.logger.error(f'Error in get_recommendations: {e}')
        return jsonify({'error': 'Internal server error'}), 500
