#!/bin/bash

# Setup Virtual Environment and Dependencies for publish-md-to-wechat

PROJECT_DIR=$(dirname "$0")
cd "$PROJECT_DIR"

echo "=================================================="
echo "🚀 Initializing WeChat Publisher Environment..."
echo "=================================================="

# Check for Python 3
if ! command -v python3 &> /dev/null
then
    echo "❌ Error: Python 3 is not installed. Please install it first."
    exit 1
fi

# Create .venv if not exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    python3 -m venv .venv
else
    echo "✅ Virtual environment already exists."
fi

# Upgrade pip and install requirements
echo "📥 Installing dependencies from requirements.txt..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Install Node dependencies for Slidev/video export
if [ "${SKIP_NODE_INSTALL:-0}" = "1" ]; then
    echo "⏭️  SKIP_NODE_INSTALL=1, skipping npm dependency install."
else
    if [ -f "package.json" ]; then
        if command -v npm &> /dev/null; then
            echo "📦 Installing Node dependencies (Slidev + Playwright-Chromium)..."
            if [ -f "package-lock.json" ]; then
                npm ci
            else
                npm install
            fi
        else
            echo "⚠️  npm not found. Install Node.js to enable video export (requires npx/npm)."
        fi
    fi
fi

# Install Playwright browser runtime (required for video slide capture)
if [ "${SKIP_PLAYWRIGHT_INSTALL:-0}" = "1" ]; then
    echo "⏭️  SKIP_PLAYWRIGHT_INSTALL=1, skipping Chromium install."
else
    echo "🎬 Installing Playwright Chromium runtime (Python)..."
    python3 -m playwright install chromium
fi

# Success
echo "=================================================="
echo "✨ Setup complete!"
echo "💡 Article publish: source .venv/bin/activate && python3 scripts/wechat_publisher.py ..."
echo "💡 Video export:   source .venv/bin/activate && python3 scripts/video_publisher.py --md article.md --no-tts"
echo "=================================================="
