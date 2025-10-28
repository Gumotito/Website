"""
Agent 3: Order Approval

Approves orders and transitions them to payment stage.
"""
from database import update_order_status, save_order_to_db
from services.langsmith_service import traceable


@traceable(name="Agent 3 - Order Approval")
def approve_order(order_id: int, order: str) -> str:
    """
    Approve an order and move to payment stage
    
    Args:
        order_id: Order ID to approve
        order: Order text
        
    Returns:
        Approval confirmation message
    """
    update_order_status(order_id, 'approved')
    save_order_to_db(order, 'awaiting_payment', agent=3)
    return f"Order #{order_id} Approved: {order}"
