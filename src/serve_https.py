"""
Inicia o servidor de produção por HTTPS usando Cheroot (WSGI + TLS).
Necessário para o modo PWA offline funcionar nos dispositivos.

Uso: python serve_https.py [porta]
Exemplo: python serve_https.py 8443

Requer os arquivos certs/cert.pem e certs/key.pem (gere com gerar_certificado.py).
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mpdft_inspecoes.settings')
os.environ.setdefault('PYTHONUTF8', '1')

from cheroot.wsgi import Server
from cheroot.ssl.builtin import BuiltinSSLAdapter
from mpdft_inspecoes.wsgi import application

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(BASE_DIR, 'certs', 'cert.pem')
KEY = os.path.join(BASE_DIR, 'certs', 'key.pem')

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get('PORT', 8443))

    if not (os.path.exists(CERT) and os.path.exists(KEY)):
        print('ERRO: certificado não encontrado.')
        print(f'  Esperado: {CERT}')
        print(f'           {KEY}')
        print('  Gere primeiro com: python gerar_certificado.py <IP-DA-VM>')
        sys.exit(1)

    server = Server(('0.0.0.0', port), application, numthreads=4)
    server.ssl_adapter = BuiltinSSLAdapter(CERT, KEY)

    print('=== Sistema de Inspecoes Prediais MPDFT (HTTPS) ===')
    print(f'Servidor seguro rodando em https://0.0.0.0:{port}')
    print(f'Acesse pela rede: https://<IP-deste-computador>:{port}')
    print('Pressione Ctrl+C para encerrar.')
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
