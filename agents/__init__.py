"""Agents package initialization"""
from .agent1_mail import process_mail
from .agent2_warehouse import update_stock_manual, fetch_from_api, sync_excel
from .agent3_approval import approve_order
from .agent4_delivery import fulfill_delivery
from .agent5_oversight import oversee_flow, generate_insights

__all__ = [
    'process_mail',
    'update_stock_manual',
    'fetch_from_api',
    'sync_excel',
    'approve_order',
    'fulfill_delivery',
    'oversee_flow',
    'generate_insights'
]
