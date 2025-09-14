#!/bin/bash

# DHIS2 PDF Automation - Dependency Fix Script
# This script helps resolve common dependency issues

set -e

echo "🔧 DHIS2 Dependency Fix Script"
echo "=============================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check current Python version in dhis environment
print_status "Checking current dhis environment..."

if conda env list | grep -q "^dhis "; then
    python_version=$(conda run -n dhis python --version 2>&1 | cut -d' ' -f2)
    print_status "Found Python $python_version in dhis environment"
    
    # Check if it's 3.10+
    if conda run -n dhis python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
        print_success "Python version is 3.10+ - compatible"
    else
        print_error "Python version is too old for some packages"
        print_status "Recreating environment with Python 3.10..."
        
        conda env remove -n dhis -y
        conda create -n dhis python=3.10 -y
        print_success "Created new dhis environment with Python 3.10"
    fi
else
    print_error "dhis environment not found"
    print_status "Creating dhis environment with Python 3.10..."
    conda create -n dhis python=3.10 -y
    print_success "Created dhis environment"
fi

# Activate environment
eval "$(conda shell.bash hook)"
conda activate dhis

print_status "Installing dependencies in clean environment..."

# Install basic packages first
pip install --upgrade pip
pip install wheel setuptools

# Install core Django packages
print_status "Installing Django packages..."
pip install Django==4.2.16
pip install djangorestframework==3.14.0
pip install django-cors-headers==4.0.0

# Install utilities
print_status "Installing utilities..."
pip install python-dotenv==1.0.0
pip install requests==2.31.0

# Install AI packages
print_status "Installing AI packages..."
pip install openai==1.54.4
pip install portkey-ai==0.1.90

# Install PDF processing with compatible versions
print_status "Installing PDF processing packages..."
pip install PyPDF2==3.0.1
pip install pdfplumber==0.7.6
pip install Pillow==9.5.0
pip install pdf2image==1.17.0

# Install browser automation
print_status "Installing browser automation..."
pip install playwright==1.40.0
pip install asyncio-throttle==1.0.2

# Optional packages (don't fail if they don't install)
print_status "Installing optional packages..."
pip install pytesseract==0.3.10 || print_warning "OCR support skipped"

print_success "Dependencies installed successfully!"

# Install Playwright browsers
print_status "Installing Playwright browsers..."
playwright install

print_success "All dependencies and browsers installed!"
print_status "You can now run: ./start.sh"