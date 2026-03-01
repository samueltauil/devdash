#!/bin/bash
# DevDash — Raspberry Pi 5 Setup Script
# Run this once on a fresh Pi to install all dependencies

set -e

echo "🚀 DevDash Setup"
echo "================"

# System packages
echo ""
echo "📦 Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-pip python3-venv python3-dev \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libfreetype6-dev libportmidi-dev \
    portaudio19-dev \
    git

# Python virtual environment
echo ""
echo "🐍 Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Core dependencies
echo ""
echo "📥 Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Voice dependencies (required)
echo ""
echo "🎤 Installing voice input packages..."
pip install faster-whisper sounddevice -q

# Config file
if [ ! -f config.yaml ]; then
    echo ""
    echo "📝 Creating config.yaml from template..."
    cp config.example.yaml config.yaml
    echo "   → Edit config.yaml with your GitHub token and repos"
fi

# Font download (DejaVu Sans — free, good for small screens)
echo ""
echo "🔤 Setting up fonts..."
FONT_DIR="devdash/assets/fonts"
mkdir -p "$FONT_DIR"
if [ ! -f "$FONT_DIR/DejaVuSans.ttf" ]; then
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf "$FONT_DIR/" 2>/dev/null || \
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf "$FONT_DIR/" 2>/dev/null || \
    echo "   → DejaVu fonts not found — will use PyGame default font"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit config.yaml with your GitHub token and repos"
echo "  2. Connect a USB microphone"
echo "  3. Run: source .venv/bin/activate && python -m devdash"
