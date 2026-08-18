"""Importa o diagnóstico de acessibilidade extraído do painel HTML original
para o banco de dados (Edificacao.sigla, LocalAcessibilidade,
CriterioAcessibilidade, Avaliacao).

Idempotente — usa get_or_create, pode ser rodado mais de uma vez sem duplicar.
Carga direta via ORM — não passa por `services.aplicar_edicao`, então avaliações
importadas por este comando não geram AvaliacaoHistorico até a primeira edição
manual feita pela interface (o histórico é uma garantia de edição, não de carga
inicial de dados).

Uso:
    python manage.py importar_painel_acessibilidade
    python manage.py importar_painel_acessibilidade --arquivo caminho/alternativo.json --usuario ana
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade

FIXTURE_PADRAO = (
    Path(__file__).resolve().parents[2] / 'fixtures' / 'painel_acessibilidade_origem.json'
)

MAPA_STATUS = {
    'OK': Avaliacao.Status.OK,
    'Pendente': Avaliacao.Status.PENDENTE,
    'Não se aplica': Avaliacao.Status.NAO_SE_APLICA,
}


class Command(BaseCommand):
    help = (
        'Importa o diagnóstico de acessibilidade (edificações, locais, '
        'critérios e avaliações) do JSON extraído do painel original.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--arquivo', default=str(FIXTURE_PADRAO))
        parser.add_argument(
            '--usuario', default='sistema',
            help='username do responsável pela carga inicial (deve existir).',
        )

    def handle(self, *args, **options):
        caminho = Path(options['arquivo'])
        if not caminho.exists():
            raise CommandError(f'Arquivo não encontrado: {caminho}')

        User = get_user_model()
        try:
            usuario = User.objects.get(username=options['usuario'])
        except User.DoesNotExist:
            raise CommandError(
                f'Usuário "{options["usuario"]}" não existe. Crie-o antes ou informe --usuario.'
            )

        with open(caminho, encoding='utf-8') as f:
            dados = json.load(f)

        localidades = dados['localidades']
        regioes = dados['regioes']
        locals_ = dados['locals']
        itens = dados['itens']
        status_lista = dados['status']
        resolucoes = dados['resolucoes']
        details = dados.get('details', {})

        with transaction.atomic():
            edificacao_por_indice = self._garantir_edificacoes(localidades)
            criterio_por_indice = {
                indice: CriterioAcessibilidade.objects.get_or_create(nome=nome)[0]
                for indice, nome in enumerate(itens)
            }

            criadas = 0
            for row in dados['rows']:
                row_id, i_loc, i_reg, i_local, i_item, i_status, i_resolucao, obs = row

                edificacao = edificacao_por_indice[i_loc]
                local, _ = LocalAcessibilidade.objects.get_or_create(
                    edificacao=edificacao, regiao=regioes[i_reg], nome=locals_[i_local],
                )

                criterio = criterio_por_indice[i_item]
                detalhe = details.get(str(row_id))
                if detalhe and detalhe.get('legal') and not criterio.base_legal:
                    criterio.base_legal = detalhe['legal']
                    criterio.save(update_fields=['base_legal'])

                status_bruto = status_lista[i_status] if i_status is not None and i_status >= 0 else None
                if status_bruto is None:
                    status_valor = Avaliacao.Status.NAO_SE_APLICA
                elif status_bruto in MAPA_STATUS:
                    status_valor = MAPA_STATUS[status_bruto]
                else:
                    raise CommandError(
                        f'Status desconhecido "{status_bruto}" na linha row_id={row_id}. '
                        f'Atualize MAPA_STATUS para incluir esse valor antes de importar.'
                    )
                resolucao_valor = (
                    resolucoes[i_resolucao] if i_resolucao is not None and i_resolucao >= 0 else ''
                )

                _, criada = Avaliacao.objects.get_or_create(
                    local=local, criterio=criterio,
                    defaults={
                        'status': status_valor,
                        'resolucao_diagnostico': resolucao_valor,
                        'observacao': obs or '',
                        'atualizado_por': usuario,
                    },
                )
                if criada:
                    criadas += 1

        self.stdout.write(self.style.SUCCESS(
            f'Importação concluída: {len(edificacao_por_indice)} edificações, '
            f'{len(criterio_por_indice)} critérios, {criadas} avaliações criadas.'
        ))

    def _garantir_edificacoes(self, localidades):
        mapa = {}
        for indice, sigla in enumerate(localidades):
            edificacao, _ = Edificacao.objects.get_or_create(sigla=sigla, defaults={'nome': sigla})
            mapa[indice] = edificacao
        return mapa
