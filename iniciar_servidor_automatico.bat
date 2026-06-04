@echo off
REM ============================================================
REM  Inicializacao AUTOMATICA do servidor (Agendador de Tarefas)
REM  Diferente do iniciar_servidor.bat: sem "pause" e com log.
REM  NAO use este para iniciar manualmente — use iniciar_servidor.bat.
REM ============================================================
chcp 65001 > nul
set PYTHONUTF8=1

REM ====== Porta do servidor (deve ser igual a do iniciar_servidor.bat) ======
set PORTA=8080
REM ==========================================================================

cd /d "%~dp0src"

call ..\.venv\Scripts\activate.bat

echo [%date% %time%] Iniciando servidor automatico na porta %PORTA% >> "%~dp0log_servidor_automatico.txt"

python manage.py migrate --noinput >> "%~dp0log_servidor_automatico.txt" 2>&1
python manage.py collectstatic --noinput >> "%~dp0log_servidor_automatico.txt" 2>&1

python serve.py %PORTA% >> "%~dp0log_servidor_automatico.txt" 2>&1
