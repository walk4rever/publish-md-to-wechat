#!/bin/bash

# Publish entry point for publish-md-to-wechat

# Get the absolute path of the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if .venv exists in the script directory
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "❌ Error: Virtual environment (.venv) not found in $SCRIPT_DIR."
    echo "💡 Please run $SCRIPT_DIR/install.sh first to set up the environment."
    exit 1
fi

# Run using the python inside .venv directly to avoid shell activation issues
# We use absolute paths to allow running this script from any directory
# This ensures that 'load_dotenv()' in python loads the .env from the USER'S current directory,
# not the script's directory.
"$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/scripts/wechat_publisher.py" "$@"
