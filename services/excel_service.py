"""
Excel Management Service

Handles Excel file reading, writing, and monitoring for stock synchronization.
"""
import pandas as pd
import os
import threading
import time
import logging
from typing import Dict, Tuple, Any
from datetime import datetime as dt
from database import log_stock_change

logger = logging.getLogger(__name__)


class ExcelService:
    """Manages Excel file operations and monitoring"""
    
    def __init__(self, excel_path: str, stock_service):
        """
        Initialize Excel service
        
        Args:
            excel_path: Path to Excel file
            stock_service: StockService instance for stock operations
        """
        self.excel_path = excel_path
        self.stock_service = stock_service
        self.last_modified_time = 0
        self.monitoring_active = False
        self.monitor_thread = None
    
    def read_stock(self) -> Tuple[bool, str, Dict[str, int]]:
        """
        Read stock data from Excel file
        
        Returns:
            (success, message, stock_dict) tuple
        """
        try:
            if not os.path.exists(self.excel_path):
                return False, f"Excel file not found: {self.excel_path}", {}
            
            # Read Excel or CSV
            if self.excel_path.endswith('.csv'):
                df = pd.read_csv(self.excel_path)
            else:
                df = pd.read_excel(self.excel_path, engine='openpyxl')
            
            # Validate required columns
            required_cols = {'Product', 'Quantity'}
            if not required_cols.issubset(df.columns):
                return False, f"Missing required columns. Need: {required_cols}", {}
            
            # Parse stock data
            stock_data = {}
            for _, row in df.iterrows():
                product = str(row['Product']).strip()
                try:
                    quantity = int(row['Quantity'])
                    if quantity >= 0:
                        stock_data[product] = quantity
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping invalid row for {product}: {e}")
                    continue
            
            return True, "Successfully read Excel file", stock_data
        
        except Exception as e:
            logger.error(f"Error reading Excel file: {e}")
            return False, f"Error reading file: {str(e)}", {}
    
    def write_stock(self, stock_data: Dict[str, int]) -> bool:
        """
        Write stock data to Excel file
        
        Args:
            stock_data: Dictionary of product: quantity
            
        Returns:
            True if successful
        """
        try:
            # Create DataFrame
            df = pd.DataFrame([
                {
                    'Product': product,
                    'Quantity': qty,
                    'Unit': 'units',
                    'Supplier': '',
                    'Last_Updated': dt.now().strftime('%Y-%m-%d')
                }
                for product, qty in stock_data.items()
            ])
            
            # Write to Excel
            df.to_excel(self.excel_path, index=False, engine='openpyxl')
            logger.info(f'Updated Excel file: {self.excel_path}')
            
            # Update modification time to prevent re-reading our own write
            self.last_modified_time = os.path.getmtime(self.excel_path)
            
            return True
        except Exception as e:
            logger.error(f'Error updating Excel file: {e}')
            return False
    
    def track_changes(self, old_stock: Dict[str, int], new_stock: Dict[str, int]) -> Dict[str, Any]:
        """
        Compare old and new stock to track changes
        
        Returns:
            Dictionary with added, removed, increased, decreased, unchanged items
        """
        changes = {
            'added': {},
            'removed': {},
            'increased': {},
            'decreased': {},
            'unchanged': {}
        }
        
        all_products = set(old_stock.keys()) | set(new_stock.keys())
        
        for product in all_products:
            old_qty = old_stock.get(product, 0)
            new_qty = new_stock.get(product, 0)
            
            if product not in old_stock:
                changes['added'][product] = new_qty
            elif product not in new_stock:
                changes['removed'][product] = old_qty
            elif new_qty > old_qty:
                changes['increased'][product] = {
                    'old': old_qty,
                    'new': new_qty,
                    'change': new_qty - old_qty
                }
            elif new_qty < old_qty:
                changes['decreased'][product] = {
                    'old': old_qty,
                    'new': new_qty,
                    'change': old_qty - new_qty
                }
            else:
                changes['unchanged'][product] = new_qty
        
        return changes
    
    def sync_from_excel(self) -> Tuple[Dict[str, Any], int]:
        """
        Read Excel and sync stock, tracking changes
        
        Returns:
            (changes_dict, change_count) tuple
        """
        # Read Excel file
        success, message, new_stock_data = self.read_stock()
        
        if not success:
            logger.error(f"Failed to sync from Excel: {message}")
            return {}, 0
        
        # Get old stock
        old_stock = self.stock_service.get_all()
        
        # Track changes
        changes = self.track_changes(old_stock, new_stock_data)
        
        # Apply new stock
        self.stock_service.update_bulk(new_stock_data)
        
        # Log all changes to database
        change_count = 0
        for product, qty in changes['added'].items():
            log_stock_change(product, qty, qty, 'excel_added')
            change_count += 1
        
        for product, old_qty in changes['removed'].items():
            log_stock_change(product, -old_qty, 0, 'excel_removed')
            change_count += 1
        
        for product, change_info in changes['increased'].items():
            log_stock_change(product, change_info['change'], change_info['new'], 'excel_increased')
            change_count += 1
        
        for product, change_info in changes['decreased'].items():
            log_stock_change(product, -change_info['change'], change_info['new'], 'excel_decreased')
            change_count += 1
        
        return changes, change_count
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        logger.info(f'Starting Excel file monitor for: {self.excel_path}')
        
        while self.monitoring_active:
            try:
                if os.path.exists(self.excel_path):
                    current_mtime = os.path.getmtime(self.excel_path)
                    
                    # Check if file was modified
                    if current_mtime != self.last_modified_time:
                        if self.last_modified_time > 0:  # Skip first check on startup
                            logger.info('Excel file modified, auto-syncing stock...')
                            
                            changes, change_count = self.sync_from_excel()
                            logger.info(f'Auto-sync complete: {change_count} changes detected')
                        
                        self.last_modified_time = current_mtime
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f'Error in Excel monitor: {e}')
                time.sleep(10)  # Wait longer on error
    
    def start_monitoring(self):
        """Start background monitoring thread"""
        if self.monitoring_active:
            logger.warning('Excel monitoring already active')
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info('Excel file monitoring started')
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.monitoring_active = False
        logger.info('Excel file monitoring stopped')
