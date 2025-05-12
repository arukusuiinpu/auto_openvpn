@echo off

cd /d "%~dp0"

call python downloader.py --help

echo Use by writing: python downloader.py [args]

cmd /K