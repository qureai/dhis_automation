#!/bin/bash

# Full stack local development script (Backend + Frontend)
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🚀 DHIS Full Stack - Local Development"
echo "======================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    
    # Kill backend if running
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    
    # Kill frontend if running
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    echo -e "${GREEN}✅ Services stopped${NC}"
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

# Check for tmux/screen (optional but recommended)
if command -v tmux &> /dev/null; then
    echo -e "${GREEN}✅ tmux detected - recommended for split terminal${NC}"
    echo "  Tip: Use 'tmux new-session -s dhis' for better experience"
elif command -v screen &> /dev/null; then
    echo -e "${GREEN}✅ screen detected - can use for multiple terminals${NC}"
else
    echo -e "${YELLOW}⚠️  Consider installing tmux or screen for better terminal management${NC}"
fi

# Parse command
MODE=${1:-split}

case $MODE in
    split|tmux)
        # Use tmux for split terminal
        if ! command -v tmux &> /dev/null; then
            echo -e "${RED}❌ tmux is not installed${NC}"
            echo "Install tmux:"
            echo "  - macOS: brew install tmux"
            echo "  - Ubuntu: sudo apt-get install tmux"
            echo "  - Or use: ./start_local_full.sh sequential"
            exit 1
        fi
        
        # Check if session exists
        if tmux has-session -t dhis 2>/dev/null; then
            echo -e "${YELLOW}tmux session 'dhis' already exists${NC}"
            echo "Attach to it? (y/n)"
            read -r attach
            if [[ "$attach" =~ ^[Yy]$ ]]; then
                tmux attach-session -t dhis
            else
                echo "Kill existing session? (y/n)"
                read -r kill_session
                if [[ "$kill_session" =~ ^[Yy]$ ]]; then
                    tmux kill-session -t dhis
                else
                    exit 1
                fi
            fi
        fi
        
        echo -e "${GREEN}Starting tmux session with backend and frontend...${NC}"
        
        # Create new tmux session with backend
        tmux new-session -d -s dhis -n backend "cd backend && ./start_local.sh"
        
        # Create new window for frontend
        tmux new-window -t dhis -n frontend "cd frontend && ./start_local.sh"
        
        # Optional: Create third window for general use
        tmux new-window -t dhis -n terminal "bash"
        
        # Display info
        echo ""
        echo -e "${GREEN}✅ Full stack started in tmux!${NC}"
        echo "======================================"
        echo -e "Backend:  ${BLUE}http://localhost:8000${NC}"
        echo -e "Frontend: ${BLUE}http://localhost:3000${NC}"
        echo ""
        echo "tmux commands:"
        echo "  Attach:        tmux attach -t dhis"
        echo "  Switch panes:  Ctrl+b then arrow keys"
        echo "  Switch windows: Ctrl+b then 0/1/2"
        echo "  Detach:        Ctrl+b then d"
        echo "  Kill session:  tmux kill-session -t dhis"
        echo ""
        
        # Attach to session
        tmux attach-session -t dhis
        ;;
    
    sequential|seq)
        # Run backend and frontend sequentially in same terminal
        echo -e "${YELLOW}Starting backend and frontend in background...${NC}"
        echo ""
        
        # Start backend
        echo -e "${GREEN}Starting backend...${NC}"
        cd backend
        ./start_local.sh runserver > ../backend.log 2>&1 &
        BACKEND_PID=$!
        cd ..
        
        # Wait for backend to start
        echo "Waiting for backend to start..."
        sleep 5
        
        # Check if backend is running
        if ! kill -0 $BACKEND_PID 2>/dev/null; then
            echo -e "${RED}❌ Backend failed to start. Check backend.log${NC}"
            exit 1
        fi
        
        echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
        
        # Start frontend
        echo -e "${GREEN}Starting frontend...${NC}"
        cd frontend
        ./start_local.sh start > ../frontend.log 2>&1 &
        FRONTEND_PID=$!
        cd ..
        
        # Wait for frontend to start
        echo "Waiting for frontend to start..."
        sleep 5
        
        # Check if frontend is running
        if ! kill -0 $FRONTEND_PID 2>/dev/null; then
            echo -e "${RED}❌ Frontend failed to start. Check frontend.log${NC}"
            kill $BACKEND_PID 2>/dev/null || true
            exit 1
        fi
        
        echo -e "${GREEN}✅ Frontend started (PID: $FRONTEND_PID)${NC}"
        
        echo ""
        echo "======================================"
        echo -e "${GREEN}✅ Full stack is running!${NC}"
        echo "======================================"
        echo -e "Backend:  ${BLUE}http://localhost:8000${NC}"
        echo -e "Frontend: ${BLUE}http://localhost:3000${NC}"
        echo -e "Logs:     ${YELLOW}tail -f backend.log frontend.log${NC}"
        echo ""
        echo "Press Ctrl+C to stop all services"
        echo ""
        
        # Keep script running and show logs
        tail -f backend.log frontend.log
        ;;
    
    parallel|bg)
        # Run in background with logs
        echo -e "${YELLOW}Starting services in background...${NC}"
        
        # Create logs directory
        mkdir -p logs
        
        # Start backend
        echo -n "Starting backend... "
        cd backend
        nohup ./start_local.sh runserver > ../logs/backend.log 2>&1 &
        BACKEND_PID=$!
        echo $BACKEND_PID > ../logs/backend.pid
        cd ..
        echo -e "${GREEN}✓${NC} (PID: $BACKEND_PID)"
        
        # Start frontend
        echo -n "Starting frontend... "
        cd frontend
        nohup ./start_local.sh start > ../logs/frontend.log 2>&1 &
        FRONTEND_PID=$!
        echo $FRONTEND_PID > ../logs/frontend.pid
        cd ..
        echo -e "${GREEN}✓${NC} (PID: $FRONTEND_PID)"
        
        # Wait a moment for services to start
        sleep 5
        
        echo ""
        echo "======================================"
        echo -e "${GREEN}✅ Services started in background${NC}"
        echo "======================================"
        echo -e "Backend:  ${BLUE}http://localhost:8000${NC}"
        echo -e "Frontend: ${BLUE}http://localhost:3000${NC}"
        echo ""
        echo "Commands:"
        echo "  View logs:     tail -f logs/*.log"
        echo "  Stop services: ./start_local_full.sh stop"
        echo "  Check status:  ./start_local_full.sh status"
        ;;
    
    stop)
        # Stop background services
        echo -e "${YELLOW}Stopping services...${NC}"
        
        # Stop backend
        if [ -f logs/backend.pid ]; then
            BACKEND_PID=$(cat logs/backend.pid)
            if kill -0 $BACKEND_PID 2>/dev/null; then
                kill $BACKEND_PID
                echo -e "${GREEN}✓${NC} Backend stopped"
            fi
            rm logs/backend.pid
        fi
        
        # Stop frontend
        if [ -f logs/frontend.pid ]; then
            FRONTEND_PID=$(cat logs/frontend.pid)
            if kill -0 $FRONTEND_PID 2>/dev/null; then
                kill $FRONTEND_PID
                echo -e "${GREEN}✓${NC} Frontend stopped"
            fi
            rm logs/frontend.pid
        fi
        
        # Kill tmux session if exists
        if tmux has-session -t dhis 2>/dev/null; then
            tmux kill-session -t dhis
            echo -e "${GREEN}✓${NC} tmux session killed"
        fi
        
        echo -e "${GREEN}✅ All services stopped${NC}"
        ;;
    
    status)
        # Check service status
        echo "Service Status:"
        echo "==============="
        
        # Check backend
        if [ -f logs/backend.pid ]; then
            BACKEND_PID=$(cat logs/backend.pid)
            if kill -0 $BACKEND_PID 2>/dev/null; then
                echo -e "Backend:  ${GREEN}✓ Running${NC} (PID: $BACKEND_PID)"
            else
                echo -e "Backend:  ${RED}✗ Stopped${NC}"
            fi
        else
            echo -e "Backend:  ${YELLOW}Not started${NC}"
        fi
        
        # Check frontend
        if [ -f logs/frontend.pid ]; then
            FRONTEND_PID=$(cat logs/frontend.pid)
            if kill -0 $FRONTEND_PID 2>/dev/null; then
                echo -e "Frontend: ${GREEN}✓ Running${NC} (PID: $FRONTEND_PID)"
            else
                echo -e "Frontend: ${RED}✗ Stopped${NC}"
            fi
        else
            echo -e "Frontend: ${YELLOW}Not started${NC}"
        fi
        
        # Check tmux session
        if tmux has-session -t dhis 2>/dev/null; then
            echo -e "tmux:     ${GREEN}✓ Session active${NC}"
        fi
        
        # Check URLs
        echo ""
        echo "URLs:"
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health/ | grep -q "200"; then
            echo -e "Backend:  ${GREEN}http://localhost:8000${NC} ✓"
        else
            echo -e "Backend:  ${RED}http://localhost:8000${NC} ✗"
        fi
        
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "200\|304"; then
            echo -e "Frontend: ${GREEN}http://localhost:3000${NC} ✓"
        else
            echo -e "Frontend: ${RED}http://localhost:3000${NC} ✗"
        fi
        ;;
    
    logs)
        # View logs
        if [ -d logs ]; then
            echo "Viewing logs (Ctrl+C to exit)..."
            tail -f logs/*.log
        else
            echo -e "${YELLOW}No log files found. Start services first.${NC}"
        fi
        ;;
    
    help|--help|-h|*)
        echo "Usage: ./start_local_full.sh [mode]"
        echo ""
        echo "Modes:"
        echo "  split/tmux   - Run in tmux with split windows (default)"
        echo "  sequential   - Run both in same terminal"
        echo "  parallel     - Run in background with nohup"
        echo "  stop         - Stop all services"
        echo "  status       - Check service status"
        echo "  logs         - View service logs"
        echo "  help         - Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./start_local_full.sh           # Start with tmux"
        echo "  ./start_local_full.sh sequential # Run in same terminal"
        echo "  ./start_local_full.sh parallel   # Run in background"
        echo "  ./start_local_full.sh stop      # Stop all services"
        echo ""
        echo "Requirements:"
        echo "  - Conda or Python 3.11+ for backend"
        echo "  - Node.js 18+ for frontend"
        echo "  - tmux (optional but recommended)"
        ;;
esac