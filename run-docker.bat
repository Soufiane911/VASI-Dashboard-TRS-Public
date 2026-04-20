@echo off
setlocal

cd /d "%~dp0"

echo Starting app-trs with Docker Compose...
docker compose up --build

endlocal
