"""Geração dos textos narrativos do Relatório Final via Gemini.

Regra de grounding (grill de 2026-10-27): o modelo só pode sintetizar os
dados fornecidos no payload — nunca inventar normas, números ou fatos.
Qualquer falha (sem API key, rede, resposta inválida) retorna todos os
campos como string vazia e NUNCA lança exceção — decisão de produto: o
relatório é sempre gerado, com ou sem os textos."""
import json
import logging
import os
from typing import Literal

from django.conf import settings
from google import genai
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TextosRelatorioFinal(BaseModel):
    sumario_executivo: str
    principais_constatacoes: str
    providencias_administracao: str
    resultados_gerais_intro: str
    resultados_gerais_achados_criticos: str
    itens_conformidade_civil: str
    itens_conformidade_eletrica: str
    itens_conformidade_mecanica: str
    manutencao_classificacao: Literal['Atende integralmente', 'Atende parcialmente', 'Não atende']
    manutencao_fundamentacao: str
    uso_classificacao: Literal['Regular', 'Regular, com ressalvas', 'Irregular']
    uso_fundamentacao: str
    plano_acao_imediato: str
    plano_acao_curto: str
    plano_acao_medio: str
    plano_acao_longo: str
    conclusao: str


CAMPOS_VAZIOS = {campo: '' for campo in TextosRelatorioFinal.model_fields}

SYSTEM_PROMPT = (
    "Você é um redator técnico que produz trechos de um Laudo Técnico de "
    "Inspeção Predial do MPDFT, a partir EXCLUSIVAMENTE dos dados JSON "
    "fornecidos nesta mensagem. Nunca invente fatos, números, normas "
    "técnicas (ABNT, IBAPE etc.) ou recomendações que não estejam "
    "literalmente presentes nos dados fornecidos — sintetize e reescreva em "
    "prosa técnica formal em português do Brasil, sem adicionar informação "
    "nova. Os campos 'manutencao_classificacao' e 'uso_classificacao' "
    "exigem exatamente uma das opções do vocabulário fechado do schema — "
    "nunca uma categoria fora da lista. Quando um texto cobrir mais de um "
    "parágrafo, separe os parágrafos com uma linha em branco (\\n\\n)."
)


def gerar_textos_relatorio(payload: dict) -> dict:
    if not settings.GEMINI_API_KEY:
        return dict(CAMPOS_VAZIOS)
    try:
        # python-decouple (config()) não propaga valores lidos do .env para
        # os.environ. genai.Client() sem argumentos lê a chave de
        # os.environ['GOOGLE_API_KEY'] ou os.environ['GEMINI_API_KEY'], então
        # é preciso espelhar settings.GEMINI_API_KEY lá antes de instanciar.
        os.environ['GEMINI_API_KEY'] = settings.GEMINI_API_KEY
        client = genai.Client()
        interaction = client.interactions.create(
            model=settings.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            input=json.dumps(payload, ensure_ascii=False),
            response_format={
                'type': 'text',
                'mime_type': 'application/json',
                'schema': TextosRelatorioFinal.model_json_schema(),
            },
        )
        textos = TextosRelatorioFinal.model_validate_json(interaction.output_text)
        return textos.model_dump()
    except Exception:
        logger.exception('Falha ao gerar textos do Relatório Final via Gemini.')
        return dict(CAMPOS_VAZIOS)
