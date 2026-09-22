#!/usr/bin/env bash
set -e
echo "Starting Campus Connect in Development Mode..."
cd "$(dirname "$0")/.."
python app.py
