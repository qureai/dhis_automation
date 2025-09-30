#!/bin/bash

# DHIS2 Medical Processing & Automation System
# Comprehensive startup script for both Frontend and Backend

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CONDA_ENV="dhis"
BACKEND_PORT=8005
FRONTEND_PORT=3000
BACKEND_DIR="backend"
FRONTEND_DIR="frontend"

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

# Function to check if conda is available
check_conda() {
    if ! command -v conda &> /dev/null; then
        print_error "Conda is not installed or not in PATH"
        print_error "Please install Miniconda/Anaconda and try again"
        exit 1
    fi
    print_success "Conda is available"
}

# Function to check if conda environment exists
check_conda_env() {
    if ! conda info --envs | grep -q "^${CONDA_ENV} "; then
        print_error "Conda environment '${CONDA_ENV}' does not exist"
        print_error "Please create the environment first:"
        print_error "conda create -n ${CONDA_ENV} python=3.10 -y"
        exit 1
    fi
    print_success "Conda environment '${CONDA_ENV}' exists"
}

# Function to activate conda environment
activate_conda() {
    print_status "Activating conda environment: ${CONDA_ENV}"
    
    # Initialize conda for bash
    if [[ -f "/opt/miniconda3/etc/profile.d/conda.sh" ]]; then
        source "/opt/miniconda3/etc/profile.d/conda.sh"
    elif [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
        source "$HOME/miniconda3/etc/profile.d/conda.sh"
    elif [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
        source "$HOME/anaconda3/etc/profile.d/conda.sh"
    else
        print_warning "Could not find conda.sh, using conda run instead"
        return 1
    fi
    
    conda activate "${CONDA_ENV}" 2>/dev/null || {
        print_warning "Could not activate environment directly, using conda run"
        return 1
    }
    
    print_success "Conda environment activated"
    return 0
}

# Function to install backend dependencies
install_backend_deps() {
    print_status "Installing backend dependencies..."
    
    if [[ -f "${BACKEND_DIR}/requirements.txt" ]]; then
        if activate_conda; then
            pip install -r "${BACKEND_DIR}/requirements.txt"
        else
            /opt/miniconda3/bin/conda run -n "${CONDA_ENV}" pip install -r "${BACKEND_DIR}/requirements.txt"
        fi
        print_success "Backend dependencies installed"
    else
        print_warning "Backend requirements.txt not found"
    fi
}

# Function to install frontend dependencies
install_frontend_deps() {
    print_status "Installing frontend dependencies..."
    
    if [[ -f "${FRONTEND_DIR}/package.json" ]]; then
        cd "${FRONTEND_DIR}"
        
        # Check if node_modules exists
        if [[ ! -d "node_modules" ]]; then
            print_status "Installing npm packages..."
            npm install
        else
            print_status "Node modules already exist, skipping npm install"
        fi
        
        cd ..
        print_success "Frontend dependencies ready"
    else
        print_warning "Frontend package.json not found"
    fi
}

# Function to run database migrations
run_migrations() {
    print_status "Running database migrations..."
    
    if activate_conda; then
        cd "${BACKEND_DIR}"
        python manage.py makemigrations --noinput || true
        python manage.py migrate --noinput
        cd ..
    else
        /opt/miniconda3/bin/conda run -n "${CONDA_ENV}" python "${BACKEND_DIR}/manage.py" makemigrations --noinput || true
        /opt/miniconda3/bin/conda run -n "${CONDA_ENV}" python "${BACKEND_DIR}/manage.py" migrate --noinput
    fi
    
    print_success "Database migrations completed"
}

# Function to check backend health
check_backend_health() {
    print_status "Checking backend health..."
    
    # Wait for backend to start
    sleep 5
    
    max_attempts=30
    attempt=0
    
    while [[ $attempt -lt $max_attempts ]]; do
        if curl -s "http://localhost:${BACKEND_PORT}/api/images/health/" > /dev/null 2>&1; then
            print_success "Backend is healthy and responding"
            return 0
        fi
        
        attempt=$((attempt + 1))
        print_status "Waiting for backend... (attempt $attempt/$max_attempts)"
        sleep 2
    done
    
    print_error "Backend health check failed after $max_attempts attempts"
    return 1
}

# Function to start backend
start_backend() {
    print_status "Starting Django backend on port ${BACKEND_PORT}..."
    
    # Check if port is already in use
    if lsof -Pi :${BACKEND_PORT} -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port ${BACKEND_PORT} is already in use"
        print_status "Attempting to kill existing process..."
        lsof -ti:${BACKEND_PORT} | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
    
    # Start backend in background
    if activate_conda; then
        cd "${BACKEND_DIR}"
        nohup python manage.py runserver "0.0.0.0:${BACKEND_PORT}" > ../backend.log 2>&1 &
        BACKEND_PID=$!
        cd ..
    else
        nohup /opt/miniconda3/bin/conda run -n "${CONDA_ENV}" python "${BACKEND_DIR}/manage.py" runserver "0.0.0.0:${BACKEND_PORT}" > backend.log 2>&1 &
        BACKEND_PID=$!
    fi
    
    echo $BACKEND_PID > .backend_pid
    print_success "Backend started with PID: $BACKEND_PID"
    
    # Health check
    if check_backend_health; then
        print_success "Backend is running successfully"
        print_status "Backend API: http://localhost:${BACKEND_PORT}"
        print_status "API Documentation:"
        print_status "  - Register Processing: http://localhost:${BACKEND_PORT}/api/images/process-register/"
        print_status "  - PDF Processing: http://localhost:${BACKEND_PORT}/api/images/process-pdf/"
        print_status "  - System Info: http://localhost:${BACKEND_PORT}/api/images/system/"
    else
        print_error "Backend failed to start properly"
        return 1
    fi
}

# Function to start frontend
start_frontend() {
    print_status "Starting React frontend on port ${FRONTEND_PORT}..."
    
    # Check if port is already in use
    if lsof -Pi :${FRONTEND_PORT} -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port ${FRONTEND_PORT} is already in use"
        print_status "Attempting to kill existing process..."
        lsof -ti:${FRONTEND_PORT} | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
    
    # Start frontend in background
    cd "${FRONTEND_DIR}"
    nohup npm start > ../frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd ..
    
    echo $FRONTEND_PID > .frontend_pid
    print_success "Frontend started with PID: $FRONTEND_PID"
    
    # Wait for frontend to be ready
    print_status "Waiting for frontend to be ready..."
    sleep 10
    
    print_success "Frontend is running successfully"
    print_status "Frontend URL: http://localhost:${FRONTEND_PORT}"
    print_status "Features available:"
    print_status "  - Home Page: http://localhost:${FRONTEND_PORT}"
    print_status "  - Patient Register Processing: Navigate to 'Patient Register'"
    print_status "  - PDF Document Automation: Navigate to 'PDF Automation'"
}

# Function to show system status
show_system_status() {
    echo ""
    echo "=========================================="
    echo "🚀 DHIS2 SYSTEM STATUS"
    echo "=========================================="
    
    # Backend status
    if [[ -f ".backend_pid" ]] && kill -0 $(cat .backend_pid) 2>/dev/null; then
        print_success "✅ Backend: Running (PID: $(cat .backend_pid))"
        print_status "   🔗 API: http://localhost:${BACKEND_PORT}"
    else
        print_error "❌ Backend: Not running"
    fi
    
    # Frontend status
    if [[ -f ".frontend_pid" ]] && kill -0 $(cat .frontend_pid) 2>/dev/null; then
        print_success "✅ Frontend: Running (PID: $(cat .frontend_pid))"
        print_status "   🔗 UI: http://localhost:${FRONTEND_PORT}"
    else
        print_error "❌ Frontend: Not running"
    fi
    
    echo ""
    echo "📋 AVAILABLE FEATURES:"
    echo "  1. Patient Register Processing (Dual Image Upload)"
    echo "  2. PDF Document Automation (Health Facility Reports)"
    echo ""
    echo "🔧 SYSTEM COMMANDS:"
    echo "  - Stop system: ./start_system.sh stop"
    echo "  - View logs: tail -f backend.log frontend.log"
    echo "  - System info: curl http://localhost:${BACKEND_PORT}/api/images/system/"
    echo "=========================================="
}

# Function to stop system
stop_system() {
    print_status "Stopping DHIS2 system..."
    
    # Stop backend
    if [[ -f ".backend_pid" ]]; then
        BACKEND_PID=$(cat .backend_pid)
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill $BACKEND_PID
            print_success "Backend stopped (PID: $BACKEND_PID)"
        fi
        rm -f .backend_pid
    fi
    
    # Stop frontend
    if [[ -f ".frontend_pid" ]]; then
        FRONTEND_PID=$(cat .frontend_pid)
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill $FRONTEND_PID
            print_success "Frontend stopped (PID: $FRONTEND_PID)"
        fi
        rm -f .frontend_pid
    fi
    
    # Kill any remaining processes on the ports
    lsof -ti:${BACKEND_PORT} | xargs kill -9 2>/dev/null || true
    lsof -ti:${FRONTEND_PORT} | xargs kill -9 2>/dev/null || true
    
    print_success "DHIS2 system stopped"
}

# Function to show logs
show_logs() {
    print_status "Showing system logs (Ctrl+C to exit)..."
    tail -f backend.log frontend.log 2>/dev/null || {
        print_warning "Log files not found. System may not be running."
    }
}

# Main function
main() {
    clear
    echo "=========================================="
    echo "🏥 DHIS2 Medical Processing System v2.0"
    echo "=========================================="
    echo ""
    
    case "${1:-start}" in
        "start")
            print_status "Starting DHIS2 Medical Processing System..."
            
            # Pre-flight checks
            check_conda
            check_conda_env
            
            # Install dependencies
            install_backend_deps
            install_frontend_deps
            
            # Prepare database
            run_migrations
            
            # Start services
            start_backend
            start_frontend
            
            # Show status
            show_system_status
            
            print_success "🎉 DHIS2 system is ready!"
            print_status "Open your browser to: http://localhost:${FRONTEND_PORT}"
            ;;
            
        "stop")
            stop_system
            ;;
            
        "status")
            show_system_status
            ;;
            
        "logs")
            show_logs
            ;;
            
        "restart")
            stop_system
            sleep 2
            main start
            ;;
            
        "help"|"-h"|"--help")
            echo "DHIS2 Medical Processing System - Startup Script"
            echo ""
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  start    Start both frontend and backend (default)"
            echo "  stop     Stop both services"
            echo "  restart  Stop and start services"
            echo "  status   Show system status"
            echo "  logs     Show live logs"
            echo "  help     Show this help message"
            echo ""
            echo "Features:"
            echo "  - Patient Register Processing (dual image upload)"
            echo "  - PDF Document Automation (health facility reports)"
            echo "  - Unified web interface with navigation"
            echo "  - DHIS2 integration with session tracking"
            ;;
            
        *)
            print_error "Unknown command: $1"
            print_status "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Handle Ctrl+C
trap 'echo -e "\n${YELLOW}[INTERRUPT]${NC} Stopping system..."; stop_system; exit 0' INT

# Run main function
main "$@"