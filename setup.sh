#!/bin/bash
# Setup script for the London Breakout trading bot
# Run: cd /home/workspace/robinhood-trading-bot && bash setup.sh

set -e

echo "=== London Breakout Trading Bot Setup ==="

# Install Python dependencies
echo "→ Installing dependencies..."
pip install pyyaml pandas yfinance requests 2>&1 | tail -1

# Create data directory
mkdir -p data

echo "✓ Done."
echo ""
echo "Next steps:"
echo "  1. Edit config.yaml with your capital and risk settings"
echo "  2. Export Robinhood credentials as env vars (or fill config.yaml):"
echo "     export RH_USERNAME=\"email@domain.com\""
echo "     export RH_PASSWORD=\"your_password\""
echo "  3. Run a dry scan:  python3 -m src.bot --symbols SPY --dry-run"
