"""
Main Routes for Website

Homepage and logs viewing routes.
"""
from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Homepage with agent dashboard"""
    return render_template('index.html')


@main_bp.route('/logs')
def logs():
    """Logs viewing page"""
    return render_template('logs.html')
