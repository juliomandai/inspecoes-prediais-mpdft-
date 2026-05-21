"""
Inicia o servidor de producao usando Waitress.
Uso: python serve.py [porta]
Exemplo: python serve.py 8080
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mpdft_inspecoes.settings')
os.environ.setdefault('PYTHONUTF8', '1')

from waitress import serve
from mpdft_inspecoes.wsgi import application

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get('PORT', 8000))
    print(f'=== Sistema de Insspecoes Prediais MPDFT ===')
    print(f'Servidor rodando em http://0.0.0.0:{port}')
    print(f'Acesse pela rede: http://<IP-deste-computador>:{port}')
    print(f'Pressione Ctrl+C para encerrar.')
    serve(application, host='0.0.0.0', port=port, threads=4)
