@echo off
echo Seeding Campus Connect database...
cd "%~dp0\.."
python seed.py
