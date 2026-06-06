"""
Gera um certificado autoassinado (cert.pem + key.pem) para servir a aplicação
por HTTPS, necessário para o modo PWA offline funcionar nos dispositivos.

Uso:
    python gerar_certificado.py <IP-DA-VM>
Exemplo:
    python gerar_certificado.py 10.34.233.23

Os arquivos são gravados em src/certs/cert.pem e src/certs/key.pem.
O certificado inclui o IP informado, além de localhost e 127.0.0.1, e tem
validade de 10 anos.
"""
import os
import sys
import ipaddress
import datetime

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

BASE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(BASE, 'src', 'certs')


def main():
    if len(sys.argv) < 2:
        print('ERRO: informe o IP da VM. Ex.: python gerar_certificado.py 10.34.233.23')
        return 1

    ip_str = sys.argv[1].strip()
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        print(f'ERRO: "{ip_str}" não é um endereço IP válido.')
        return 1

    os.makedirs(DEST, exist_ok=True)
    cert_path = os.path.join(DEST, 'cert.pem')
    key_path = os.path.join(DEST, 'key.pem')

    # Chave privada RSA 2048
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    nome = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'BR'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'MPDFT'),
        x509.NameAttribute(NameOID.COMMON_NAME, ip_str),
    ])

    sans = [
        x509.IPAddress(ip_obj),
        x509.IPAddress(ipaddress.ip_address('127.0.0.1')),
        x509.DNSName('localhost'),
    ]

    agora = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - datetime.timedelta(days=1))
        .not_valid_after(agora + datetime.timedelta(days=3650))  # 10 anos
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    with open(key_path, 'wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(cert_path, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print('Certificado gerado com sucesso!')
    print(f'  Certificado: {cert_path}')
    print(f'  Chave:       {key_path}')
    print(f'  Válido para: {ip_str}, 127.0.0.1, localhost')
    print(f'  Validade:    10 anos')
    print()
    print('Para os dispositivos confiarem no certificado, instale o arquivo')
    print('cert.pem como "Autoridade de Certificação Raiz Confiável" em cada')
    print('tablet/computador (veja o guia CONFIGURAR_HTTPS.md).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
