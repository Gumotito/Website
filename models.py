"""
Data Models for Website Multi-Agent System

Pydantic models for request validation and data integrity.
"""
from pydantic import BaseModel, field_validator, Field
from typing import List


class OrderItem(BaseModel):
    """Single item in an order"""
    product: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(..., gt=0)
    
    @field_validator('product')
    @classmethod
    def product_alphanumeric(cls, v):
        """Validate product name is alphanumeric"""
        if not v.replace(' ', '').replace('-', '').replace('_', '').isalnum():
            raise ValueError('Product name must be alphanumeric')
        return v.strip()


class StockUpdate(BaseModel):
    """Stock update request with multiple items"""
    items: List[OrderItem]


class Order(BaseModel):
    """Order text validation"""
    order_text: str = Field(..., min_length=3, max_length=1000)
