#!/bin/bash
# Wrapper script to run the CRIMSONBCT Netlist Editor on Linux
# This script suppresses graphical warnings and driver issues when running under WSLg

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_PATH="${SCRIPT_DIR}/build-qt6-linux-starfish/bin/CRIMSONBCT"

if [[ ! -f "${BIN_PATH}" ]]; then
    echo "Error: Could not find CRIMSONBCT binary at ${BIN_PATH}"
    echo "Please build the NetlistEditor first."
    exit 1
fi

# Check if running under Windows Subsystem for Linux (WSL)
if grep -qi microsoft /proc/version; then
    # Fix QStandardPaths warnings
    export XDG_RUNTIME_DIR=/run/user/$(id -u)
    
    # Suppress libEGL / ZINK hardware acceleration errors by forcing software rendering
    export LIBGL_ALWAYS_SOFTWARE=1
    export GALLIUM_DRIVER=llvmpipe
    
    # Force X11 backend to avoid Wayland composition issues on some WSL versions
    export QT_QPA_PLATFORM=xcb
fi

exec "${BIN_PATH}" "$@"
