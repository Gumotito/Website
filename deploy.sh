#!/bin/bash
cd ~/website
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
# Touch the wsgi file to reload
touch /var/www/gumotito_pythonanywhere_com_wsgi.py