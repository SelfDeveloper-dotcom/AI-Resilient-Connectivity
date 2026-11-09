@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo AI Resilient Connectivity - Local Knowledge RAG Setup
echo ============================================================
echo.
where ollama >nul 2>&1
if errorlevel 1 (
  echo Ollama is not installed or is not on PATH.
  echo Install Ollama for Windows from https://ollama.com/download
  echo Then re-run this script.
  exit /b 1
)
echo Ollama detected.
echo.
echo Pulling semantic embedding model...
ollama pull embeddinggemma
if errorlevel 1 exit /b 1
echo.
echo Pulling local answer-generation model...
ollama pull qwen3:4b
if errorlevel 1 exit /b 1
echo.
echo Models are ready.
echo Restart the dashboard with: .\run_dashboard.bat
endlocal
