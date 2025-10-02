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

# Detect which group is used for serial ports (dialout or uucp)
detect_serial_group() {
    local SERIAL_GROUP=""
    
    # First, check actual serial devices if they exist
    if ls -l /dev/ttyUSB* 2>/dev/null | grep -q uucp; then
        SERIAL_GROUP="uucp"
    elif ls -l /dev/ttyUSB* 2>/dev/null | grep -q dialout; then
        SERIAL_GROUP="dialout"
    # If no devices, check which group exists
    elif getent group uucp > /dev/null 2>&1; then
        SERIAL_GROUP="uucp"
    elif getent group dialout > /dev/null 2>&1; then
        SERIAL_GROUP="dialout"
    else
        # Fallback - no standard group found
        SERIAL_GROUP="root"
    fi
    
    echo "$SERIAL_GROUP"
}

# Check and setup CP210x USB-to-UART driver
check_cp210x_driver() {
    echo_info "Checking CP210x USB-to-UART driver..."
    
    # Check if driver is loaded
    if ! lsmod | grep -q cp210x; then
        echo_warn "CP210x driver not loaded. Loading..."
        if sudo modprobe cp210x 2>/dev/null; then
            echo_info "CP210x driver loaded successfully"
        else
            echo_error "Failed to load CP210x driver"
            return 1
        fi
    else
        echo_info "CP210x driver is already loaded"
    fi
    
    # Check if custom Product ID (840e) needs to be added
    echo_info "Checking for custom USB device support..."
    
    # Check if device with ID 10c4:840e is connected
    if lsusb | grep -q "10c4:840e"; then
        echo_info "Found device with ID 10c4:840e"
        
        # Try to add custom ID to driver
        if [ -w "/sys/bus/usb-serial/drivers/cp210x/new_id" ]; then
            echo_info "Adding custom Product ID (840e) to CP210x driver..."
            if echo "10c4 840e" | sudo tee /sys/bus/usb-serial/drivers/cp210x/new_id > /dev/null 2>&1; then
                echo_info "Custom Product ID added successfully"
                sleep 1
            else
                echo_warn "Device may already be registered or driver needs reload"
            fi
        fi
    fi
    
    return 0
}

# Setup udev rules for CP210x device
setup_udev_rules() {
    echo_info "Checking udev rules for CP210x device..."
    
    # Detect which group is used for serial ports
    SERIAL_GROUP=$(detect_serial_group)
    if [ "$SERIAL_GROUP" = "uucp" ]; then
        echo_info "Detected serial group: uucp (Manjaro/Arch)"
    else
        echo_info "Detected serial group: dialout"
    fi
    
    UDEV_RULE_FILE="/etc/udev/rules.d/99-cp210x.rules"
    UDEV_RULE_CONTENT="# CP210x USB to Serial - allow access for ${SERIAL_GROUP} group
SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"10c4\", ATTRS{idProduct}==\"ea60\", MODE=\"0666\", GROUP=\"${SERIAL_GROUP}\"
SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"10c4\", ATTRS{idProduct}==\"840e\", MODE=\"0666\", GROUP=\"${SERIAL_GROUP}\"

# Auto-load custom Product ID
ACTION==\"add\", SUBSYSTEM==\"usb\", ATTR{idVendor}==\"10c4\", ATTR{idProduct}==\"840e\", RUN+=\"/bin/sh -c 'echo 10c4 840e > /sys/bus/usb-serial/drivers/cp210x/new_id'\""
    
    # Check if rules file exists and has correct content
    if [ -f "$UDEV_RULE_FILE" ]; then
        if grep -q "10c4.*840e" "$UDEV_RULE_FILE"; then
            echo_info "udev rules for CP210x already exist"
        else
            echo_warn "Updating udev rules for CP210x..."
            echo "$UDEV_RULE_CONTENT" | sudo tee "$UDEV_RULE_FILE" > /dev/null
            sudo udevadm control --reload-rules
            sudo udevadm trigger
            echo_info "udev rules updated"
        fi
    else
        echo_info "Creating udev rules for CP210x..."
        echo "$UDEV_RULE_CONTENT" | sudo tee "$UDEV_RULE_FILE" > /dev/null
        sudo udevadm control --reload-rules
        sudo udevadm trigger
        echo_info "udev rules created"
    fi
}

# Check user permissions for serial port access
check_serial_permissions() {
    echo_info "Checking user permissions for serial port access..."
    
    # Detect which group is used for serial ports
    SERIAL_GROUP=$(detect_serial_group)
    if [ "$SERIAL_GROUP" = "uucp" ]; then
        echo_info "System uses uucp group for serial ports (Manjaro/Arch)"
    else
        echo_info "System uses dialout group for serial ports"
    fi
    
    # Check if user is in the appropriate group
    if groups | grep -qE "dialout|uucp"; then
        echo_info "User is already in serial port group ($(groups | grep -oE 'dialout|uucp'))"
    elif [ "$SERIAL_GROUP" = "root" ]; then
        echo_warn "No standard serial port group found (dialout/uucp)"
        echo_warn "Serial ports may require root access"
    else
        echo_warn "User is not in ${SERIAL_GROUP} group"
        echo_info "Adding user to ${SERIAL_GROUP} group..."
        
        if sudo usermod -a -G "$SERIAL_GROUP" "$USER"; then
            echo_info "User added to ${SERIAL_GROUP} group"
            echo_warn "⚠️  IMPORTANT: You need to log out and log back in for group changes to take effect"
            echo_warn "Or run: newgrp ${SERIAL_GROUP}"
        else
            echo_error "Failed to add user to ${SERIAL_GROUP} group"
            echo_warn "You may need to manually configure serial port access"
        fi
    fi
    
    # Check for available serial ports
    if ls /dev/ttyUSB* 2>/dev/null; then
        echo_info "Available serial ports:"
        ls -l /dev/ttyUSB* 2>/dev/null || true
    else
        echo_warn "No /dev/ttyUSB* devices found. Make sure your device is connected."
    fi
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
    
    # Check and setup CP210x driver
    echo_info ""
    echo_info "--- USB Device Setup ---"
    check_cp210x_driver
    setup_udev_rules
    check_serial_permissions
    echo_info ""
    
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
