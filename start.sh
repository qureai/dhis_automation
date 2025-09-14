#!/bin/bash

# DHIS2 PDF Automation - Startup Script
# This script starts both frontend and backend servers

set -e  # Exit on any error

echo "🚀 Starting DHIS2 PDF Automation System"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if conda environment exists
conda_env_exists() {
    conda env list | grep -q "^$1 "
}

# Check prerequisites
print_status "Checking prerequisites..."

# Check if conda is installed
if ! command_exists conda; then
    print_error "Conda is not installed or not in PATH"
    exit 1
fi

# Check if node is installed
if ! command_exists node; then
    print_error "Node.js is not installed or not in PATH"
    exit 1
fi

# Check if npm is installed
if ! command_exists npm; then
    print_error "npm is not installed or not in PATH"
    exit 1
fi

print_success "All prerequisites found"

# Check if dhis conda environment exists
if ! conda_env_exists "dhis"; then
    print_error "Conda environment 'dhis' does not exist"
    print_status "Creating conda environment 'dhis' with Python 3.10..."
    conda create -n dhis python=3.10 -y
    print_success "Created conda environment 'dhis'"
else
    # Check Python version in existing environment
    print_status "Checking Python version in 'dhis' environment..."
    python_version=$(conda run -n dhis python --version 2>&1 | cut -d' ' -f2)
    print_status "Found Python $python_version in dhis environment"
    
    # Check if Python version is 3.10 or higher
    if ! conda run -n dhis python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
        print_warning "Python version in dhis environment is too old (need 3.10+)"
        print_status "Recreating dhis environment with Python 3.10..."
        conda env remove -n dhis -y
        conda create -n dhis python=3.10 -y
        print_success "Recreated conda environment 'dhis' with Python 3.10"
    fi
fi

# Create backend .env file from .env.example if it doesn't exist
BACKEND_ENV_FILE="backend/.env"
if [ ! -f "$BACKEND_ENV_FILE" ]; then
    if [ -f ".env.example" ]; then
        print_status "Creating backend .env file from .env.example..."
        cp .env.example "$BACKEND_ENV_FILE"
        print_success "Created $BACKEND_ENV_FILE"
        print_warning "Please edit $BACKEND_ENV_FILE with your actual credentials"
    else
        print_error ".env.example file not found"
        exit 1
    fi
else
    print_status "Backend .env file already exists"
fi

# Install backend dependencies
print_status "Setting up backend environment..."
cd backend

# Activate conda environment and install dependencies
eval "$(conda shell.bash hook)"
conda activate dhis

if [ ! -f "requirements_installed.flag" ]; then
    print_status "Installing backend dependencies..."
    
    # Upgrade pip first
    pip install --upgrade pip
    
    # Install requirements with error handling
    if pip install -r requirements.txt; then
        touch requirements_installed.flag
        print_success "Backend dependencies installed"
    else
        print_warning "Main requirements.txt failed, trying minimal requirements..."
        
        # Try minimal requirements file
        if pip install -r requirements-minimal.txt; then
            touch requirements_installed.flag
            print_success "Minimal backend dependencies installed"
        else
            print_error "Failed to install dependencies from both requirements files"
            print_status "Trying to install critical dependencies individually..."
            
            # Install critical packages individually with fallbacks
            pip install "Django==4.2.16" || print_warning "Django installation had issues"
            pip install "djangorestframework==3.14.0" || print_warning "DRF installation had issues"
            pip install "django-cors-headers==4.0.0" || print_warning "CORS headers installation had issues"
            pip install "python-dotenv==1.0.0" || print_warning "python-dotenv installation had issues"
            pip install "playwright==1.40.0" || print_warning "Playwright installation had issues"
            pip install "portkey-ai==0.1.90" || print_warning "Portkey AI installation had issues"
            pip install "openai==1.54.4" || print_warning "OpenAI installation had issues"
            
            # Mark as installed even if some optional packages failed
            touch requirements_installed.flag
            print_warning "Backend dependencies partially installed - some optional packages may be missing"
        fi
    fi
else
    print_status "Backend dependencies already installed"
fi

# Run Django migrations
print_status "Running Django migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# Install Playwright browsers if not already installed
if [ ! -d "$HOME/.cache/ms-playwright" ] || [ -z "$(ls -A "$HOME/.cache/ms-playwright" 2>/dev/null)" ]; then
    print_status "Installing Playwright browsers..."
    playwright install
    print_success "Playwright browsers installed"
fi

print_success "Backend setup complete"
cd ..

# Install frontend dependencies
print_status "Setting up frontend environment..."
cd frontend

if [ ! -d "node_modules" ]; then
    print_status "Installing frontend dependencies..."
    npm install
    print_success "Frontend dependencies installed"
else
    print_status "Frontend dependencies already installed"
fi

cd ..

# Function to cleanup on exit
cleanup() {
    print_status "Shutting down servers..."
    
    # Kill log tail processes
    if [ ! -z "$TAIL_BACKEND_PID" ]; then
        kill $TAIL_BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$TAIL_FRONTEND_PID" ]; then
        kill $TAIL_FRONTEND_PID 2>/dev/null || true
    fi
    
    # Kill server processes
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    print_success "Shutdown complete"
}

# Set trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Start backend server
print_status "Starting Django backend server on port 8005..."
cd backend

# Ensure conda environment is activated and environment variables are loaded
eval "$(conda shell.bash hook)"
conda activate dhis

# Export environment variables for the Django process
set -a  # Automatically export all variables
source .env
set +a  # Stop automatically exporting

print_status "Environment variables loaded from .env"
print_status "PORTKEY_API_KEY present: $([ -n "$PORTKEY_API_KEY" ] && echo "Yes" || echo "No")"
print_status "DHIS_USERNAME present: $([ -n "$DHIS_USERNAME" ] && echo "Yes" || echo "No")"

python manage.py runserver 8005 > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait a bit for backend to start
sleep 3

# Check if backend started successfully
if kill -0 $BACKEND_PID 2>/dev/null; then
    print_success "Backend server started (PID: $BACKEND_PID)"
    print_status "Backend URL: http://localhost:8005"
    print_status "Backend API: http://localhost:8005/api/"
    print_status "Admin Panel: http://localhost:8005/admin/"
else
    print_error "Failed to start backend server"
    print_status "Check backend.log for details"
    exit 1
fi

# Start frontend server
print_status "Starting React frontend server on port 3001..."
cd frontend

# Set environment variable to use port 3001
export PORT=3001

npm start > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait a bit for frontend to start
sleep 5

# Check if frontend started successfully
if kill -0 $FRONTEND_PID 2>/dev/null; then
    print_success "Frontend server started (PID: $FRONTEND_PID)"
    print_status "Frontend URL: http://localhost:3001"
else
    print_error "Failed to start frontend server"
    print_status "Check frontend.log for details"
    exit 1
fi

# Display startup summary
echo ""
echo "🎉 DHIS2 PDF Automation System is running!"
echo "=========================================="
echo "Frontend:    http://localhost:3001"
echo "Backend API: http://localhost:8005/api/"
echo "Admin Panel: http://localhost:8005/admin/"
echo ""
echo "📋 Real-time Logs:"
echo ""

# Function to show logs with prefixes
show_logs() {
    tail -f backend.log 2>/dev/null | sed 's/^/[BACKEND] /' &
    TAIL_BACKEND_PID=$!
    
    tail -f frontend.log 2>/dev/null | sed 's/^/[FRONTEND] /' &
    TAIL_FRONTEND_PID=$!
    
    wait
}


echo "Press Ctrl+C to stop all servers and logs"
echo "=========================================="

# Show real-time logs
show_logs