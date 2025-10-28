"""
Agent 5: Flow Oversight

Monitors workflow performance and generates improvement recommendations.
"""
import logging
from typing import Dict, List, Any
from database import get_db_connection
from services.langsmith_service import traceable

logger = logging.getLogger(__name__)


@traceable(name="Agent 5 - Flow Oversight")
def oversee_flow(stock_service) -> Dict[str, Any]:
    """
    Monitor and analyze workflow performance
    
    Args:
        stock_service: StockService instance
        
    Returns:
        Dictionary of workflow metrics
    """
    conn = get_db_connection()
    try:
        # Count orders by status
        received = conn.execute("SELECT COUNT(*) FROM orders WHERE status='received'").fetchone()[0]
        approved = conn.execute("SELECT COUNT(*) FROM orders WHERE status='approved'").fetchone()[0]
        awaiting_payment = conn.execute("SELECT COUNT(*) FROM orders WHERE status='awaiting_payment'").fetchone()[0]
        awaiting_delivery = conn.execute("SELECT COUNT(*) FROM orders WHERE status='awaiting_delivery'").fetchone()[0]
        delivered = conn.execute("SELECT COUNT(*) FROM orders WHERE status='delivered'").fetchone()[0]
        
        # Stock metrics
        current_stock = stock_service.get_all()
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
        logger.error(f'Error in oversee_flow: {e}')
        return {}
    finally:
        conn.close()


def generate_insights(metrics: Dict[str, Any]) -> List[str]:
    """
    Generate improvement recommendations based on metrics
    
    Args:
        metrics: Workflow metrics dictionary
        
    Returns:
        List of insight strings
    """
    insights = []
    
    # Check for bottlenecks
    if metrics.get('pending_approval', 0) > 2:
        insights.append("⚠️  Multiple orders awaiting approval - consider faster approval process")
    
    if metrics.get('pending_payment', 0) > 3:
        insights.append("⚠️  Multiple orders awaiting payment - send payment reminders")
    
    if metrics.get('pending_delivery', 0) > 2:
        insights.append("⚠️  Delivery backlog detected - allocate more resources")
    
    # Stock warnings
    low_stock = metrics.get('low_stock_items', [])
    if low_stock:
        insights.append(f"📦 Low stock items: {', '.join(low_stock)} - Reorder soon")
    
    # Performance insights
    total_received = metrics.get('total_received', 0)
    total_delivered = metrics.get('total_delivered', 0)
    
    if total_received > 0 and total_delivered > 0:
        delivery_rate = (total_delivered / total_received) * 100
        insights.append(f"✅ Delivery rate: {delivery_rate:.1f}%")
    
    return insights
