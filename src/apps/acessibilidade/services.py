from django.db import transaction

CAMPOS_EDITAVEIS = [
    'status', 'resolucao_diagnostico', 'observacao',
    'status_acao', 'responsavel', 'prazo', 'resolucao_prevista',
    'ordem_servico', 'data_os', 'notas',
]


def _snapshot(avaliacao):
    dados = {}
    for campo in CAMPOS_EDITAVEIS:
        valor = getattr(avaliacao, campo)
        dados[campo] = valor.isoformat() if hasattr(valor, 'isoformat') else valor
    return dados


@transaction.atomic
def aplicar_edicao(avaliacao, patch, usuario):
    """Aplica um patch de campos editáveis a uma avaliação, salva, e registra
    um AvaliacaoHistorico imutável com o estado completo antes/depois.
    Único ponto de entrada para editar uma Avaliacao — garante o invariante
    de que toda edição deixa rastro (ADR-05)."""
    from .models import AvaliacaoHistorico

    snapshot_anterior = _snapshot(avaliacao)
    for campo, valor in patch.items():
        if campo in CAMPOS_EDITAVEIS:
            setattr(avaliacao, campo, valor)
    avaliacao.atualizado_por = usuario
    avaliacao.save()
    snapshot_novo = _snapshot(avaliacao)

    AvaliacaoHistorico.objects.create(
        avaliacao=avaliacao,
        snapshot_anterior=snapshot_anterior,
        snapshot_novo=snapshot_novo,
        editado_por=usuario,
    )
    return avaliacao


@transaction.atomic
def aplicar_edicao_lote(avaliacoes, patch, usuario):
    """Aplica o mesmo patch a várias avaliações, cada uma gerando seu próprio
    registro de histórico independente (não um histórico único de lote)."""
    for avaliacao in avaliacoes:
        aplicar_edicao(avaliacao, patch, usuario)
