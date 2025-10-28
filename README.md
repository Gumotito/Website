# Multi-Agent Order Management System

An intelligent Flask-based web application featuring a 5-agent workflow system for processing orders, managing inventory, and providing real-time analytics. Built with enterprise-grade security, data persistence, and performance optimizations.

## 🎯 Features

### 🤖 Five Intelligent Agents
1. **Agent 1 - Mail Interface**: Processes incoming orders and verifies stock availability
2. **Agent 2 - Warehouse**: Manages inventory levels with thread-safe operations
3. **Agent 3 - Order Approval**: Reviews and approves orders before payment
4. **Agent 4 - Delivery/Fulfillment**: Handles order fulfillment and stock deduction
5. **Agent 5 - Flow Oversight**: Provides real-time metrics, insights, and recommendations

### 🔐 Security & Reliability
- **Thread-Safe Operations**: All stock operations protected with `threading.Lock()`
- **Input Validation**: Pydantic models prevent injection attacks
- **Rate Limiting**: Flask-Limiter protects against abuse
- **Comprehensive Logging**: RotatingFileHandler with full audit trail
- **Error Handling**: Try-catch blocks throughout with structured error responses

### 💾 Data Persistence
- **SQLite Database**: All orders persist across restarts
- **Stock History**: Complete audit trail of inventory changes
- **Atomic Operations**: No partial order failures
- **Pagination**: Efficient handling of large datasets

### 📊 Monitoring & Analytics
- **Real-Time Metrics**: Order counts, pending approvals, delivery tracking
- **Performance Insights**: Bottleneck detection and efficiency analysis
- **AI Recommendations**: Automated suggestions for process improvements
- **Stock Alerts**: Low inventory warnings

### 🔬 LangSmith Integration
- Optional LangSmith tracing for debugging and monitoring
- Agent performance tracking
- Tool call analysis

## 📁 Project Structure

```
website/
├── app.py                  # Main application (657 lines, fully refactored)
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── IMPROVEMENTS.md        # Detailed refactoring documentation
├── deploy.sh              # Deployment script
├── .env                   # Environment variables (not in repo)
├── orders.db              # SQLite database (auto-created)
├── stock.json             # Stock persistence file
├── logs/
│   └── website.log        # Application logs (10MB max, 3 backups)
├── static/
│   └── style.css          # Frontend styling
└── templates/
    ├── index.html         # Main dashboard
    └── logs.html          # Order logs viewer
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip package manager

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Gumotito/Website.git
   cd Website
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **(Optional) Configure LangSmith Tracing**:
   Create a `.env` file:
   ```env
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=your_api_key_here
   LANGCHAIN_PROJECT=website-agents
   ```

5. **Run the application**:
   ```bash
   python app.py
   ```

6. **Access the application**:
   Open your browser to `http://127.0.0.1:5000`

## 📖 Usage Guide

### Processing an Order

1. **Agent 1 - Submit Order**:
   - Format: `Product A:5, Product B:10`
   - System checks stock availability
   - Order saved to database

2. **Agent 2 - Update Warehouse**:
   - Format: `Product A:100units, Product B:50units`
   - Stock levels updated atomically
   - Changes logged to audit trail

3. **Agent 3 - Approve Order**:
   - Review stock verification
   - Click "Approve Order"
   - Order moves to payment stage

4. **Agent 4 - Fulfill Delivery**:
   - Payment confirmed
   - Click "Mark as Fulfilled"
   - Stock automatically deducted
   - Order marked as delivered

5. **Agent 5 - Monitor Performance**:
   - View real-time metrics
   - Review bottleneck alerts
   - Get AI-powered recommendations

### API Endpoints

#### Order Management
- `POST /agent/1/mail` - Submit new order (10 req/min)
- `POST /agent/2/warehouse` - Update stock (20 req/min)
- `POST /agent/3/approve` - Approve order (15 req/min)
- `POST /agent/4/fulfilled` - Fulfill order (10 req/min)
- `POST /agent/4/delivery-complete` - Mark as delivered

#### Analytics
- `GET /agent/5/oversight` - Get metrics and insights
- `GET /agent/5/recommendations` - Get AI recommendations

#### Data Access
- `GET /api/logs?page=1&per_page=50` - Paginated order logs

## 🛠️ Technical Stack

- **Framework**: Flask 3.0.0
- **Database**: SQLite3 with thread-safe connections
- **Validation**: Pydantic 2.12.3
- **Rate Limiting**: Flask-Limiter 3.5.0
- **CORS**: Flask-CORS 6.0.1
- **Logging**: RotatingFileHandler (stdlib)
- **Tracing**: LangSmith (optional)
- **Type Hints**: Full typing support

## 📊 Database Schema

### orders
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
order_text TEXT NOT NULL
status TEXT NOT NULL  -- received, approved, awaiting_payment, awaiting_delivery, delivered
timestamp TEXT NOT NULL
agent INTEGER
details TEXT
```

### order_items
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
order_id INTEGER NOT NULL
product TEXT NOT NULL
quantity INTEGER NOT NULL
FOREIGN KEY (order_id) REFERENCES orders(id)
```

### stock_history
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
product TEXT NOT NULL
quantity_change INTEGER NOT NULL
new_quantity INTEGER NOT NULL
reason TEXT
timestamp TEXT NOT NULL
```

## 🔒 Security Features

1. **Input Validation**: Pydantic models with strict rules
2. **Rate Limiting**: Prevents API abuse
3. **Thread Safety**: No race conditions on stock updates
4. **SQL Injection Protection**: Parameterized queries
5. **Error Sanitization**: No sensitive data in error messages

## 📈 Performance Optimizations

1. **Connection Pooling**: Efficient database access
2. **Pagination**: Handles large datasets
3. **Atomic Operations**: Thread-safe with minimal lock contention
4. **Caching**: Stock availability checks optimized
5. **Lazy Loading**: Database connections created on-demand

## 🐛 Debugging

### View Logs
```bash
# Real-time monitoring
tail -f logs/website.log

# Windows
Get-Content logs\website.log -Wait
```

### Access Database
```bash
sqlite3 orders.db
.schema  # View schema
SELECT * FROM orders WHERE status='awaiting_payment';
SELECT * FROM stock_history ORDER BY timestamp DESC LIMIT 10;
```

### Check Rate Limits
Rate limit headers are included in responses:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

## 📚 Documentation

For detailed information about the refactoring and improvements, see [IMPROVEMENTS.md](IMPROVEMENTS.md).

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- Built with Flask framework
- LangSmith integration for agent tracing
- Inspired by multi-agent workflow systems

## 📞 Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Status**: ✅ Production Ready  
**Last Updated**: October 28, 2025  
**Version**: 2.0.0 (Complete Refactoring)

## License

This project is licensed under the MIT License.