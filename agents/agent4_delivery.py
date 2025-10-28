"""
Agent 4: Delivery Fulfillment

Fulfills orders by deducting stock and updating Excel file.
"""
import logging
from typing import Tuple
from database import save_order_to_db, log_stock_change
from services.langsmith_service import traceable

logger = logging.getLogger(__name__)


@traceable(name="Agent 4 - Delivery Fulfillment")
def fulfill_delivery(order: str, stock_service, excel_service) -> Tuple[bool, str]:
    """
    Fulfill order delivery by deducting stock
    
    Args:
        order: Order text like "Product A: 5, Product B: 10"
        stock_service: StockService instance
        excel_service: ExcelService instance for updating Excel
        
    Returns:
        (success, message) tuple
    """
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
                success, message = stock_service.deduct(prod_name, qty_ordered)
                if not success:
                    failed_items.append(f"{prod_name}: {message}")
                else:
                    new_qty = stock_service.get(prod_name)
                    log_stock_change(prod_name, -qty_ordered, new_qty, 'order_fulfillment')
            except ValueError:
                failed_items.append(f"{prod_name}: Invalid quantity format")
    
    if failed_items:
        return False, "Fulfillment failed:\n" + "\n".join(failed_items)
    
    # Update Excel file with current stock after successful delivery
    current_stock = stock_service.get_all()
    excel_updated = excel_service.write_stock(current_stock)
    if not excel_updated:
        logger.warning('Order fulfilled but Excel update failed')
    
    return True, f"Order Fulfilled: {order}"
