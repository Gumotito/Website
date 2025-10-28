"""
Stock Management Service

Thread-safe stock operations with JSON persistence.
"""
import threading
import json
import os
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class StockService:
    """Manages stock inventory with thread-safe operations"""
    
    def __init__(self, stock_file: str = None):
        """
        Initialize stock service
        
        Args:
            stock_file: Path to stock JSON file (default: stock.json in current dir)
        """
        self.lock = threading.RLock()  # Use RLock for reentrant locking
        self.stock = {}
        
        if stock_file is None:
            self.stock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'stock.json')
        else:
            self.stock_file = stock_file
        
        self.load()
    
    def load(self):
        """Load stock from JSON file"""
        with self.lock:
            try:
                with open(self.stock_file, 'r') as f:
                    self.stock = json.load(f)
                    logger.info(f'Loaded stock: {len(self.stock)} items')
            except FileNotFoundError:
                self.stock = {}
                logger.info('No existing stock file, starting fresh')
            except Exception as e:
                logger.error(f'Error loading stock: {e}')
                self.stock = {}
    
    def save(self):
        """Save stock to JSON file"""
        with self.lock:
            try:
                with open(self.stock_file, 'w') as f:
                    json.dump(self.stock, f, indent=2)
            except Exception as e:
                logger.error(f'Error saving stock: {e}')
    
    def get_all(self) -> Dict[str, int]:
        """Get all stock items (thread-safe copy)"""
        with self.lock:
            return dict(self.stock)
    
    def get(self, product: str) -> int:
        """Get stock quantity for a product"""
        with self.lock:
            return self.stock.get(product, 0)
    
    def update(self, product: str, quantity: int) -> bool:
        """
        Update stock quantity for a product
        
        Args:
            product: Product name
            quantity: New quantity
            
        Returns:
            True if successful
        """
        with self.lock:
            self.stock[product] = quantity
            self.save()
            return True
    
    def update_bulk(self, stock_dict: Dict[str, int]):
        """
        Update multiple products at once
        
        Args:
            stock_dict: Dictionary of product: quantity
        """
        with self.lock:
            self.stock.update(stock_dict)
            self.save()
    
    def deduct(self, product: str, quantity: int) -> Tuple[bool, str]:
        """
        Deduct stock with validation
        
        Args:
            product: Product name
            quantity: Quantity to deduct
            
        Returns:
            (success, message) tuple
        """
        with self.lock:
            if product not in self.stock:
                return False, f'Product {product} not found in stock'
            if self.stock[product] < quantity:
                return False, f'Insufficient stock for {product}: need {quantity}, have {self.stock[product]}'
            
            self.stock[product] -= quantity
            self.save()
            return True, 'Stock deducted successfully'
    
    def check_availability(self, product: str, quantity: int) -> Tuple[bool, int]:
        """
        Check if sufficient stock is available
        
        Args:
            product: Product name
            quantity: Required quantity
            
        Returns:
            (is_available, current_quantity) tuple
        """
        with self.lock:
            available = self.stock.get(product, 0)
            return available >= quantity, available
    
    def add(self, product: str, quantity: int) -> bool:
        """
        Add stock (increase quantity)
        
        Args:
            product: Product name
            quantity: Quantity to add
            
        Returns:
            True if successful
        """
        with self.lock:
            current = self.stock.get(product, 0)
            self.stock[product] = current + quantity
            self.save()
            return True
