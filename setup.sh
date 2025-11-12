

# SMMA Crossover Alert System - Setup Script
# This script sets up the Python environment and installs dependencies

echo "=================================================="
echo "SMMA Crossover Alert System - Setup"
echo "=================================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "✓ Found: $PYTHON_VERSION"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    # Windows
    source venv/Scripts/activate
else
    # Linux/Mac
    source venv/bin/activate
fi

echo "✓ Virtual environment activated"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✓ Dependencies installed successfully"
echo ""

# Check if .env exists, if not create from template
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your SMTP credentials"
    echo ""
    echo "For Gmail users:"
    echo "1. Enable 2-Factor Authentication"
    echo "2. Generate App Password: https://myaccount.google.com/apppasswords"
    echo "3. Use the 16-character password in SMTP_PASSWORD"
    echo ""
else
    echo "✓ .env file already exists"
    echo ""
fi

echo "=================================================="
echo "Setup Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Configure .env file with your email credentials"
echo "2. Run: python3 smma_monitor.py"
echo ""
echo "To activate virtual environment in the future:"
echo "  Linux/Mac: source venv/bin/activate"
echo "  Windows:   .\\\\venv\\\\Scripts\\\\activate"
echo ""
