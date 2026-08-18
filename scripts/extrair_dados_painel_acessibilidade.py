"""Extrai o bloco de dados (`<script id="data-holder">`) do HTML do painel de
acessibilidade original e salva como JSON, para ser consumido pelo comando de
importação `importar_painel_acessibilidade`.

Uso:
    python scripts/extrair_dados_painel_acessibilidade.py <caminho_do_html> <caminho_de_saida.json>
"""
import json
import re
import sys


def extrair(caminho_html):
    with open(caminho_html, encoding='utf-8') as f:
        conteudo = f.read()
    m = re.search(
        r'<script id="data-holder" type="application/json">(\{.*?\})</script>',
        conteudo, re.S,
    )
    if not m:
        raise SystemExit('Bloco <script id="data-holder"> não encontrado no HTML.')
    return json.loads(m.group(1))


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Uso: extrair_dados_painel_acessibilidade.py <html> <saida.json>')
    dados = extrair(sys.argv[1])
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False)
    print(f'{len(dados["rows"])} avaliações extraídas para {sys.argv[2]}')


if __name__ == '__main__':
    main()
