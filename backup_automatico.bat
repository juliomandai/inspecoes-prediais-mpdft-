@echo off
chcp 65001 > nul
set PYTHONUTF8=1

cd /d "%~dp0"

REM Ativa o ambiente virtual e executa o backup,
REM registrando a saida no arquivo de log.
call .venv\Scripts\activate.bat
python backup_automatico.py >> "%~dp0log_backup_automatico.txt" 2>&1
