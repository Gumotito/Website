"""
Agent 2: Warehouse Stock Management

Manages stock updates, Excel synchronization, and external API integration.
"""
import logging
import requests
from typing import List, Tuple, Dict, Optional
from database import log_stock_change
from services.langsmith_service import traceable

logger = logging.getLogger(__name__)


@traceable(name="Agent 2 - Stock Update")
def update_stock_manual(stock_text: str, stock_service) -> List[str]:
    """
    Manual stock update from text input
    
    Args:
        stock_text: Text like "Product A: 50, Product B: 100"
        stock_service: StockService instance
        
    Returns:
        List of updated items
    """
    items = stock_text.split(',')
    updated_items = []
    
    for item in items:
        if ':' in item:
            product, qty_str = item.split(':')
            product = product.strip()
            try:
                qty = int(''.join(filter(str.isdigit, qty_str.strip())))
                old_qty = stock_service.get(product)
                stock_service.update(product, qty)
                log_stock_change(product, qty - old_qty, qty, 'manual_update')
                updated_items.append(f"{product}: {qty}")
            except ValueError as e:
                logger.error(f'Error parsing quantity for {product}: {e}')
                
    return updated_items


@traceable(name="Agent 2 - API Stock Fetch")
def fetch_from_api(api_url: str, stock_service, api_key: Optional[str] = None) -> Tuple[bool, str, int]:
    """
    Fetch stock data from external API
    
    Args:
        api_url: API endpoint URL
        stock_service: StockService instance
        api_key: Optional API key for authentication
        
    Returns:
        (success, message, items_updated) tuple
    """
    try:
        headers = {}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Assume API returns {"stock": {"Product A": 100, "Product B": 50}}
        if 'stock' not in data:
            return False, "Invalid API response format - missing 'stock' key", 0
        
        stock_data = data['stock']
        items_updated = 0
        
        for product, quantity in stock_data.items():
            try:
                qty = int(quantity)
                if qty >= 0:
                    old_qty = stock_service.get(product)
                    stock_service.update(product, qty)
                    log_stock_change(product, qty - old_qty, qty, 'api_import')
                    items_updated += 1
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid product {product}: {e}")
        
        return True, f"Successfully imported {items_updated} items from API", items_updated
    
    except requests.exceptions.Timeout:
        return False, "API request timed out", 0
    except requests.exceptions.RequestException as e:
        return False, f"API request failed: {str(e)}", 0
    except Exception as e:
        logger.error(f"Error fetching from API: {e}")
        return False, f"Error: {str(e)}", 0


def sync_excel(excel_service) -> Dict:
    """
    Sync stock from Excel file
    
    Args:
        excel_service: ExcelService instance
        
    Returns:
        Dictionary with sync results
    """
    try:
        logger.info('sync_excel called')
        changes, change_count = excel_service.sync_from_excel()
        logger.info(f'Sync complete: {change_count} changes')
        
        return {
            'success': True,
            'changes': changes,
            'change_count': change_count
        }
    except Exception as e:
        logger.error(f'Error in sync_excel: {e}', exc_info=True)
        return {
            'success': False,
            'changes': {
                'added': {},
                'removed': {},
                'increased': {},
                'decreased': {},
                'unchanged': {}
            },
            'change_count': 0,
            'error': str(e)
        }
