"""Test Agent 2 Excel reading directly"""
import sys
sys.path.insert(0, 'D:/Python_Projects/website')

from services import StockService, ExcelService

# Initialize services
stock_service = StockService()
excel_service = ExcelService('D:/Python_Projects/website/stock_data.xlsx', stock_service)

print("=" * 60)
print("Testing Excel Service")
print("=" * 60)

# Test 1: Read Excel
print("\n1. Reading Excel file...")
success, message, data = excel_service.read_stock()
print(f"   Success: {success}")
print(f"   Message: {message}")
print(f"   Products found: {list(data.keys()) if data else 'None'}")

# Test 2: Sync from Excel
print("\n2. Syncing stock from Excel...")
changes, change_count = excel_service.sync_from_excel()
print(f"   Changes detected: {change_count}")
print(f"   Added: {list(changes['added'].keys())}")
print(f"   Current stock: {stock_service.get_all()}")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)
