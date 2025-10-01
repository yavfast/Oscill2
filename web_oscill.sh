#!/bin/bash

# web_oscill.sh - Script for managing web_oscill server
# 
# Features:
# - Check and create Python venv if needed
# - Install required dependencies
# - Stop any running instance
# - Start the server
# - Open browser with the web page

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
WEB_OSCILL_DIR="$SCRIPT_DIR/web_oscill"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
PORT=8000
HOST="127.0.0.1"
URL="http://${HOST}:${PORT}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python is available
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo_error "Python not found. Please install Python 3.8 or higher."
        exit 1
    fi
    
    # Check Python version
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    echo_info "Found Python $PYTHON_VERSION"
}

# Check and create venv if needed
setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo_info "Virtual environment not found. Creating..."
        $PYTHON_CMD -m venv "$VENV_DIR"
        echo_info "Virtual environment created at $VENV_DIR"
    else
        echo_info "Virtual environment found at $VENV_DIR"
    fi
}

# Activate venv and install dependencies
install_dependencies() {
    echo_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    
    # Check if requirements are already installed
    if [ -f "$REQUIREMENTS_FILE" ]; then
        echo_info "Checking dependencies..."
        
        # Upgrade pip first
        python -m pip install --upgrade pip --quiet
        
        # Install or update requirements
        echo_info "Installing/updating dependencies from requirements.txt..."
        pip install -r "$REQUIREMENTS_FILE" --quiet
        
        echo_info "Dependencies installed successfully"
    else
        echo_warn "requirements.txt not found at $REQUIREMENTS_FILE"
        echo_info "Installing minimal dependencies..."
        pip install fastapi uvicorn[standard] pyserial --quiet
    fi
}

# Stop any running web_oscill instance
stop_running_instances() {
    echo_info "Checking for running web_oscill instances..."
    
    # Find processes running uvicorn with web_oscill.main:app
    PIDS=$(pgrep -f "uvicorn.*web_oscill.main:app" || true)
    
    if [ -n "$PIDS" ]; then
        echo_warn "Found running web_oscill instance(s). Stopping..."
        for PID in $PIDS; do
            echo_info "Killing process $PID"
            kill $PID 2>/dev/null || true
        done
        
        # Wait a bit for processes to terminate
        sleep 2
        
        # Force kill if still running
        PIDS=$(pgrep -f "uvicorn.*web_oscill.main:app" || true)
        if [ -n "$PIDS" ]; then
            echo_warn "Force killing remaining processes..."
            for PID in $PIDS; do
                kill -9 $PID 2>/dev/null || true
            done
        fi
        
        echo_info "Stopped previous instances"
    else
        echo_info "No running instances found"
    fi
}

# Start the web_oscill server
start_server() {
    echo_info "Starting web_oscill server..."
    
    # Activate venv
    source "$VENV_DIR/bin/activate"
    
    cd "$SCRIPT_DIR"
    
    # Start uvicorn in background
    nohup python -m uvicorn web_oscill.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --log-level info \
        > "$SCRIPT_DIR/web_oscill.log" 2>&1 &
    
    SERVER_PID=$!
    echo_info "Server started with PID: $SERVER_PID"
    
    # Wait a bit for server to start
    echo_info "Waiting for server to start..."
    sleep 3
    
    # Check if server is running
    if ps -p $SERVER_PID > /dev/null 2>&1; then
        echo_info "Server is running successfully"
        echo_info "Log file: $SCRIPT_DIR/web_oscill.log"
        return 0
    else
        echo_error "Server failed to start. Check log: $SCRIPT_DIR/web_oscill.log"
        tail -20 "$SCRIPT_DIR/web_oscill.log"
        return 1
    fi
}

# Open browser
open_browser() {
    echo_info "Opening browser at $URL"
    
    # Wait a bit more to ensure server is ready
    sleep 1
    
    # Try to open browser (works on most Linux systems)
    if command -v xdg-open &> /dev/null; then
        xdg-open "$URL" &> /dev/null &
    elif command -v gnome-open &> /dev/null; then
        gnome-open "$URL" &> /dev/null &
    elif command -v firefox &> /dev/null; then
        firefox "$URL" &> /dev/null &
    elif command -v google-chrome &> /dev/null; then
        google-chrome "$URL" &> /dev/null &
    elif command -v chromium-browser &> /dev/null; then
        chromium-browser "$URL" &> /dev/null &
    else
        echo_warn "Could not detect browser. Please open manually: $URL"
        return
    fi
    
    echo_info "Browser opened"
}

# Main execution
main() {
    echo_info "=== Web Oscill Launcher ==="
    echo_info "Script directory: $SCRIPT_DIR"
    
    # Check Python
    check_python
    
    # Setup venv
    setup_venv
    
    # Install dependencies
    install_dependencies
    
    # Stop running instances
    stop_running_instances
    
    # Start server
    if start_server; then
        # Open browser
        open_browser
        
        echo_info ""
        echo_info "=== Web Oscill is running ==="
        echo_info "URL: $URL"
        echo_info "Log file: $SCRIPT_DIR/web_oscill.log"
        echo_info ""
        echo_info "To stop the server, run:"
        echo_info "  pkill -f 'uvicorn.*web_oscill.main:app'"
        echo_info "Or check PID with:"
        echo_info "  pgrep -f 'uvicorn.*web_oscill.main:app'"
    else
        echo_error "Failed to start server"
        exit 1
    fi
}

# Run main function
main
