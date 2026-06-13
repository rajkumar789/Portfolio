#!/bin/bash
echo "Building project dependencies..."
python3 -m pip install --break-system-packages -r requirements.txt
echo "Collecting static files..."
python3 manage.py collectstatic --noinput --clear
echo "Build complete."
