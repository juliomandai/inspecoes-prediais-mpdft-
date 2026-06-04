@echo off
title Sistema de Inspecoes Prediais - MPDFT
chcp 65001 > nul
set PYTHONUTF8=1

REM ====== Porta do servidor (troque aqui se precisar) ======
set PORTA=8080
REM =========================================================

cd /d "%~dp0src"

echo Ativando ambiente virtual...
call ..\.venv\Scripts\activate.bat

echo Instalando/atualizando dependencias...
pip install -r requirements.txt --quiet

echo Aplicando migracoes pendentes...
python manage.py migrate --noinput

echo Coletando arquivos estaticos...
python manage.py collectstatic --noinput --clear

echo.
echo ============================================
echo  Sistema de Inspecoes Prediais MPDFT
echo  Porta: %PORTA%
echo ============================================
python serve.py %PORTA%

pause
