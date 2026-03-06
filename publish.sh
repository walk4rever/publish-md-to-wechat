#!/bin/bash

# Publish entry point for publish-md-to-wechat

# Get the absolute path of the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Error: Virtual environment (.venv) not found."
    echo "💡 Please run ./install.sh first to set up the environment."
    exit 1
fi

# Run using the python inside .venv directly to avoid shell activation issues
./.venv/bin/python3 scripts/wechat_publisher.py "$@"
