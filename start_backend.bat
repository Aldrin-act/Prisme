@echo off
cd /d "%~dp0"
echo Demarrage du backend PRISME sur http://localhost:8000 ...
python -m uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
