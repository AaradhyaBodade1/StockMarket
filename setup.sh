#!/bin/bash

# Setup script for Nifty Indicator Application
# This script sets up a Python virtual environment and installs dependencies.

set -e  # Exit the script on error

echo "=========================================="
echo "Nifty Indicator Application Setup"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

if [ $? -ne 0 ]; then
    echo "Error: Python 3 is not installed."
    exit 1
fi

echo ""
echo "Creating virtual environment..."
python3 -m venv venv

echo ""
echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Upgrading pip..."
pip install --upgrade pip

echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env"
echo "   cp .env.example .env"
echo ""
echo "2. Edit .env and add your SMTP credentials"
echo "   nano .env  (or use your favorite editor)"
echo ""
echo "3. Activate the virtual environment"
echo "   source venv/bin/activate"
echo ""
echo "4. Run the application"
echo "   python nifty_indicator.py"
echo ""
echo "5. (Optional) Set up cron job for automated execution"
echo "   crontab -e"
echo '   Add: 0 9 * * 1-5 cd /path/to/app && source venv/bin/activate && python nifty_indicator.py'
echo ""
echo "=========================================="
