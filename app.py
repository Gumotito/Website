"""
Website Multi-Agent System

Main Flask application orchestrating 5 agents for order processing workflow.
"""
from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv

# Import services
from services import StockService, ExcelService, setup_langsmith
from database import init_db

# Import routes
from routes import main_bp, api_bp, agent_bp

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['STOCK_FILE'] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'stock_data.xlsx'
)

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')

handler = RotatingFileHandler('logs/website.log', maxBytes=10000000, backupCount=3)
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Website startup')

# Setup LangSmith (optional)
if setup_langsmith():
    app.logger.info('LangSmith tracing enabled')

# Initialize services
app.stock_service = StockService()
app.excel_service = ExcelService(app.config['STOCK_FILE'], app.stock_service)

# Initialize database
init_db()

# Setup rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

# Register blueprints first
app.register_blueprint(main_bp)
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(agent_bp, url_prefix='/agent')

# Apply rate limits to specific routes after registration
with app.app_context():
    limiter.limit("10 per minute")(app.view_functions['agent.mail_agent'])
    limiter.limit("20 per minute")(app.view_functions['agent.warehouse_agent'])
    limiter.limit("15 per minute")(app.view_functions['agent.approve_order'])
    limiter.limit("10 per minute")(app.view_functions['agent.fulfilled_delivery_route'])

# Start Excel monitoring
app.excel_service.start_monitoring()
app.logger.info('Excel file monitoring started')


if __name__ == '__main__':
    app.run(debug=True)
