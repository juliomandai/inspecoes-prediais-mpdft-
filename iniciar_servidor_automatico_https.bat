@echo off
REM ============================================================
REM  Inicializacao AUTOMATICA do servidor HTTPS (Agendador)
REM  Sem "pause" e com log. NAO use para iniciar manualmente —
REM  para isso use iniciar_servidor_https.bat.
REM ============================================================
chcp 65001 > nul
set PYTHONUTF8=1

REM ====== Porta HTTPS (igual a do iniciar_servidor_https.bat) ======
set PORTA=8443
REM ================================================================

cd /d "%~dp0src"

call ..\.venv\Scripts\activate.bat

echo [%date% %time%] Iniciando servidor HTTPS automatico na porta %PORTA% >> "%~dp0log_servidor_automatico_https.txt"

python manage.py migrate --noinput >> "%~dp0log_servidor_automatico_https.txt" 2>&1
python manage.py collectstatic --noinput >> "%~dp0log_servidor_automatico_https.txt" 2>&1

python serve_https.py %PORTA% >> "%~dp0log_servidor_automatico_https.txt" 2>&1
