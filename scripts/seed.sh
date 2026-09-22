#!/usr/bin/env bash
set -e
echo "Seeding Campus Connect database..."
cd "$(dirname "$0")/.."
python seed.py
