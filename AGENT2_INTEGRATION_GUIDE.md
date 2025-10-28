# Agent 2 - Warehouse Stock Monitoring Guide

## Overview
Agent 2 **monitors** a dedicated Excel file (`stock_data.xlsx`) and automatically tracks all changes when you click "Read Excel File". It compares the current state with the previous state to show:
- ✅ Products added
- 📈 Products with increased quantities
- 📉 Products with decreased quantities  
- ❌ Products removed
- ➡️ Products unchanged

This approach allows external systems, ERP software, or manual edits to update the Excel file, and Agent 2 will detect and report all changes.

---

## How It Works

### 1. File Location
The system reads from: **`stock_data.xlsx`** in the root directory

### 2. Workflow
```
External System/User → Updates stock_data.xlsx → Click "Read Excel" → Agent 2 detects changes → Updates database
```

### 3. Change Tracking
Agent 2 maintains a history of the previous stock state and compares it with the new Excel data to detect:
- New products that didn't exist before
- Removed products that are no longer in Excel
- Quantity increases or decreases for existing products

---

## Excel File Format

### Required Columns
| Column | Type | Required | Description |
|--------|------|----------|-------------|
| Product | Text | ✅ Yes | Product name (unique identifier) |
| Quantity | Number | ✅ Yes | Current stock quantity |

### Optional Columns
| Column | Type | Description |
|--------|------|-------------|
| Unit | Text | Unit of measurement (e.g., "units", "boxes") |
| Supplier | Text | Supplier name |
| Last_Updated | Date | Last update timestamp |
| Category | Text | Product category |
| SKU | Text | Stock keeping unit |

### Example Excel Structure
```csv
Product,Quantity,Unit,Supplier,Last_Updated
Laptop,50,units,TechSupply Co,2025-10-28
Smartphone,120,units,MobileWorld,2025-10-28
Tablet,75,units,TechSupply Co,2025-10-27
Monitor,40,units,DisplayPro,2025-10-28
```

### Important Rules
- ✅ Product names are case-sensitive ("Laptop" ≠ "laptop")
- ✅ Quantities must be non-negative integers (0 or positive)
- ✅ Duplicate products: Last occurrence wins
- ❌ Merged cells: Not supported
- ❌ Complex formulas: Values only (formulas evaluated to numbers are OK)

---

## Usage Guide

### Method 1: Web Interface

### Format
```
Product A:10units, Product B:15units, Product C:5units
```

### Example
```
Laptop:50, Smartphone:120, Tablet:75
```

### Usage
1. Click "Manual Entry" tab
2. Enter stock data in the format above
3. Click "Update Stock"

---

## 2. Excel Upload

### Required Excel Format

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| Product | Text | ✅ Yes | Product name |
| Quantity | Number | ✅ Yes | Stock quantity |
| Unit | Text | ❌ Optional | Unit of measurement |
| Supplier | Text | ❌ Optional | Supplier name |
| Last_Updated | Date | ❌ Optional | Last update date |

### Sample Excel File
Download the sample file from the interface: `stock_data.xlsx`

Example content:
```csv
Product,Quantity,Unit,Supplier,Last_Updated
Laptop,50,units,TechSupply Co,2025-10-28
Smartphone,120,units,MobileWorld,2025-10-28
Tablet,75,units,TechSupply Co,2025-10-27
```

### Usage
1. Click "Excel Upload" tab
2. Prepare your Excel file with required columns
3. Click "Choose File" and select your .xlsx, .xls, or .csv file
4. Click "Upload Excel"
5. Stock will be updated automatically

### Supported File Types
- `.xlsx` - Excel 2007+
- `.xls` - Excel 97-2003
- `.csv` - Comma-separated values

### File Size Limit
- Maximum: 16MB

---

## 3. API Integration

### API Response Format

Your API must return JSON in one of these formats:

**Format 1: Simple Array**
```json
[
  {"product": "Laptop", "quantity": 50},
  {"product": "Smartphone", "quantity": 120},
  {"product": "Tablet", "quantity": 75}
]
```

**Format 2: Wrapped Array**
```json
{
  "products": [
    {"product": "Laptop", "quantity": 50},
    {"product": "Smartphone", "quantity": 120}
  ]
}
```

### Required Fields
- `product` (string) - Product name
- `quantity` (number) - Stock quantity

### Usage
1. Click "API Integration" tab
2. Enter your API URL (e.g., `https://api.example.com/stock`)
3. (Optional) Enter API Key if authentication is required
4. Click "Fetch from API"

### Authentication
If your API requires authentication:
- The API key will be sent in the `Authorization` header
- Format: `Authorization: Bearer YOUR_API_KEY`

### Example API URLs
```
https://api.yourcompany.com/v1/stock
https://inventory.example.com/api/products
```

### API Requirements
- **Method**: GET
- **Timeout**: 10 seconds
- **Content-Type**: application/json
- **Status Code**: 200 OK

---

## Technical Implementation

### Backend Endpoints

**POST /agent/2/warehouse**

Supports three request types:

#### 1. Manual Entry (JSON)
```bash
curl -X POST http://localhost:5000/agent/2/warehouse \
  -H "Content-Type: application/json" \
  -d '{"stock": "Laptop:50, Smartphone:120"}'
```

#### 2. Excel Upload (multipart/form-data)
```bash
curl -X POST http://localhost:5000/agent/2/warehouse \
  -F "file=@stock_data.xlsx"
```

#### 3. API Integration (JSON)
```bash
curl -X POST http://localhost:5000/agent/2/warehouse \
  -H "Content-Type: application/json" \
  -d '{
    "api_url": "https://api.example.com/stock",
    "api_key": "your-api-key-here"
  }'
```

### Response Format
```json
{
  "response": "Stock Updated from Excel:\n\nSuccessfully imported 15 products\n\nLaptop: 50 units\nSmartphone: 120 units...",
  "method": "excel",
  "count": 15
}
```

### Rate Limiting
- **Limit**: 20 requests per minute
- Applies to all three methods

---

## Database Integration

All stock updates are logged to the database:

### stock_history Table
```sql
CREATE TABLE stock_history (
    id INTEGER PRIMARY KEY,
    product TEXT NOT NULL,
    quantity_change INTEGER NOT NULL,
    new_quantity INTEGER NOT NULL,
    reason TEXT,
    timestamp TEXT NOT NULL
)
```

### Reasons Logged
- `manual_update` - Manual entry via text input
- `excel_import` - Excel file upload
- `api_import` - API integration fetch

### Example Query
```sql
SELECT * FROM stock_history 
WHERE reason = 'excel_import' 
ORDER BY timestamp DESC 
LIMIT 10;
```

---

## Error Handling

### Common Errors

**1. Excel Upload Errors**
- ❌ "Missing required columns. Need: Product, Quantity"
  - **Fix**: Ensure your Excel has columns named exactly "Product" and "Quantity"

- ❌ "Invalid file type. Use .xlsx, .xls, or .csv"
  - **Fix**: Check file extension is correct

- ❌ "Error reading file"
  - **Fix**: Ensure Excel file is not corrupted and is properly formatted

**2. API Integration Errors**
- ❌ "API request failed: Connection timeout"
  - **Fix**: Check API URL is correct and accessible

- ❌ "API response must be a list of products"
  - **Fix**: Ensure API returns correct JSON format (see above)

- ❌ "Missing required field: api_url"
  - **Fix**: Enter API URL before clicking "Fetch from API"

**3. Manual Entry Errors**
- ❌ "No valid stock items to update"
  - **Fix**: Check format is correct (Product:Quantity, Product:Quantity)

---

## Best Practices

### Excel Files
1. ✅ Use the sample file as a template
2. ✅ Keep file size under 10MB for best performance
3. ✅ Validate data before uploading (no negative quantities)
4. ✅ Use consistent product names
5. ❌ Don't include merged cells or complex formatting

### API Integration
1. ✅ Test API endpoint manually first (using Postman or curl)
2. ✅ Implement proper authentication on your API
3. ✅ Ensure API responds within 10 seconds
4. ✅ Return only active/available products
5. ❌ Don't expose sensitive data in API responses

### General
1. ✅ Start with small test imports
2. ✅ Check stock levels after import
3. ✅ Review logs for errors
4. ✅ Keep backups of your Excel files
5. ✅ Monitor rate limits

---

## Troubleshooting

### Excel Not Uploading
1. Check file size (max 16MB)
2. Verify file is not open in Excel
3. Try saving as .csv first
4. Check console logs for errors

### API Not Responding
1. Verify API URL is correct
2. Test API in browser or Postman
3. Check network connectivity
4. Verify API key if required
5. Review server logs: `tail -f logs/website.log`

### Stock Not Updating
1. Check database was initialized: Look for "Database initialized successfully" in logs
2. Verify stock.json file exists and is writable
3. Check for validation errors in response
4. Review stock_history table for changes

---

## Future Enhancements

Planned features:
- [ ] Scheduled API fetching (cron jobs)
- [ ] Multi-sheet Excel support
- [ ] Bulk product deletion
- [ ] Stock level alerts via email
- [ ] Export current stock to Excel
- [ ] API webhook support
- [ ] Real-time stock sync

---

## Support

For issues or questions:
1. Check logs: `logs/website.log`
2. Review database: `sqlite3 orders.db`
3. Open GitHub issue
4. Contact support team

**Last Updated**: October 28, 2025
