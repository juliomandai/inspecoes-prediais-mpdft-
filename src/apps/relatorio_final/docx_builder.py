"""Renderiza o Relatório Final em .docx a partir do template construído na
Task 9 (`templates_docx/relatorio_final_modelo.docx`) — preenchido com
docxtpl, que resolve `{{ }}` e `{%tr %}`/`{%p %}` sobre o próprio arquivo
Word sem recriar formatação.

Decisão de simplificação do MVP (fotos nas tabelas 10/11): as tabelas de
fotos do template (grade de 2 colunas) exigem imagens dinâmicas por achado
não conforme — fora do escopo desta task, será tratado numa integração
futura junto com a view que gera o relatório de verdade. Quando
implementadas, as fotos de cada achado serão inseridas em sequência (uma
abaixo da outra, com legenda), não como grade fixa de 2 colunas — mais
simples de implementar corretamente com docxtpl + InlineImage, dado que a
quantidade de fotos por achado varia (0 a 2).
"""
import io
from pathlib import Path

from docxtpl import DocxTemplate

TEMPLATE_PATH = Path(__file__).parent / 'templates_docx' / 'relatorio_final_modelo.docx'


def gerar_docx_relatorio(contexto: dict) -> bytes:
    tpl = DocxTemplate(str(TEMPLATE_PATH))
    tpl.render(contexto)
    buffer = io.BytesIO()
    tpl.save(buffer)
    return buffer.getvalue()
