#!/bin/bash

# DHIS2 Medical Processing System - Environment Setup Script
# Run this once to set up the conda environment and dependencies

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

CONDA_ENV="dhis"

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

# Check if conda is available
check_conda() {
    if ! command -v conda &> /dev/null; then
        print_error "Conda is not installed!"
        echo ""
        echo "Please install Miniconda or Anaconda:"
        echo "  - Miniconda: https://docs.conda.io/en/latest/miniconda.html"
        echo "  - Anaconda: https://www.anaconda.com/products/distribution"
        exit 1
    fi
    print_success "Conda is available"
}

# Create conda environment
create_conda_env() {
    print_status "Creating conda environment: ${CONDA_ENV}"
    
    if conda info --envs | grep -q "^${CONDA_ENV} "; then
        print_warning "Environment '${CONDA_ENV}' already exists"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            conda env remove -n "${CONDA_ENV}" -y
        else
            print_status "Using existing environment"
            return 0
        fi
    fi
    
    conda create -n "${CONDA_ENV}" python=3.10 -y
    print_success "Conda environment created successfully"
}

# Install backend dependencies
install_backend_deps() {
    print_status "Installing backend dependencies..."
    
    if [[ -f "backend/requirements.txt" ]]; then
        /opt/miniconda3/bin/conda run -n "${CONDA_ENV}" pip install -r backend/requirements.txt
        print_success "Backend dependencies installed"
    else
        print_error "Backend requirements.txt not found"
        exit 1
    fi
}

# Install Node.js and frontend dependencies
setup_frontend() {
    print_status "Setting up frontend..."
    
    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        print_warning "Node.js is not installed"
        print_status "Installing Node.js via conda..."
        /opt/miniconda3/bin/conda run -n "${CONDA_ENV}" conda install nodejs npm -y
    else
        print_success "Node.js is available"
    fi
    
    # Install frontend dependencies
    if [[ -d "frontend" ]] && [[ -f "frontend/package.json" ]]; then
        cd frontend
        npm install
        cd ..
        print_success "Frontend dependencies installed"
    else
        print_error "Frontend directory or package.json not found"
        exit 1
    fi
}

# Create .env file if it doesn't exist
setup_env_file() {
    print_status "Setting up environment file..."
    
    if [[ ! -f "backend/.env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example backend/.env
            print_success "Environment file created from .env.example"
            print_warning "Please edit backend/.env with your configuration"
        else
            print_warning "No .env.example found, creating basic .env file"
            cat > backend/.env << EOF
# DHIS2 Medical Processing System Configuration
PORTKEY_API_KEY=your_portkey_key_here

# Optional DHIS2 Integration
ENABLE_DHIS_INTEGRATION=False
DHIS_USERNAME=your_username
DHIS_PASSWORD=your_password
DHIS_URL=your_dhis_instance

# Optional S3 Storage
USE_S3_STORAGE=False
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_STORAGE_BUCKET_NAME=your_bucket
EOF
            print_success "Basic .env file created"
        fi
    else
        print_success "Environment file already exists"
    fi
}

# Run initial database migrations
setup_database() {
    print_status "Setting up database..."
    
    /opt/miniconda3/bin/conda run -n "${CONDA_ENV}" python backend/manage.py makemigrations --noinput
    /opt/miniconda3/bin/conda run -n "${CONDA_ENV}" python backend/manage.py migrate --noinput
    
    print_success "Database setup completed"
}

# Main setup function
main() {
    clear
    echo "=========================================="
    echo "🛠️  DHIS2 System Environment Setup"
    echo "=========================================="
    echo ""
    
    print_status "Setting up DHIS2 Medical Processing System..."
    echo ""
    
    # Run setup steps
    check_conda
    create_conda_env
    install_backend_deps
    setup_frontend
    setup_env_file
    setup_database
    
    echo ""
    echo "=========================================="
    print_success "🎉 Setup completed successfully!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Edit backend/.env with your API keys and configuration"
    echo "2. Start the system: ./start_system.sh"
    echo ""
    echo "Available commands:"
    echo "  ./start_system.sh        - Start both frontend and backend"
    echo "  ./start_system.sh stop   - Stop the system"
    echo "  ./start_system.sh status - Check system status"
    echo "  ./start_system.sh help   - Show help"
    echo ""
    echo "The system will be available at:"
    echo "  Frontend: http://localhost:3000"
    echo "  Backend:  http://localhost:8005"
    echo "=========================================="
}

# Run main function
main "$@"