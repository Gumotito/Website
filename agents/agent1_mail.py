"""
Agent 1: Mail Processing

Receives and processes incoming mail orders, performs initial stock validation.
"""
from typing import Tuple
from database import save_order_to_db
from utils import check_stock_text
from services.langsmith_service import traceable


@traceable(name="Agent 1 - Mail Processing")
def process_mail(mail_text: str, stock_dict: dict) -> Tuple[str, int]:
    """
    Process incoming mail order
    
    Args:
        mail_text: Raw order text from mail
        stock_dict: Current stock dictionary for validation
        
    Returns:
        (response_message, order_id) tuple
    """
    # Save to database
    order_id = save_order_to_db(mail_text, 'received', agent=1)
    
    # Check stock
    order_check = check_stock_text(mail_text, stock_dict)
    
    return (
        f"Order #{order_id} Received:\n\n{mail_text}\n\n"
        f"--- Stock Verification ---\n{order_check}",
        order_id
    )
