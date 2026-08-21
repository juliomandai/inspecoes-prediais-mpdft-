"""Corrige o campo `nome` das edificações que o painel de acessibilidade
importou usando a sigla como nome provisório (ex.: nome='PJSA'), substituindo
pelo nome por extenso.

Só atualiza uma edificação se o `nome` atual for exatamente igual à `sigla`
(placeholder) — não sobrescreve um nome já definido manualmente por outra via
(ex.: BSBI, que já é usado pelo módulo de Visitas Técnicas e não deve ser
alterado por este comando).

Idempotente — pode ser rodado mais de uma vez sem efeito colateral.

Uso:
    python manage.py renomear_edificacoes_acessibilidade
    python manage.py renomear_edificacoes_acessibilidade --dry-run
"""
from django.core.management.base import BaseCommand

from apps.edificacoes.models import Edificacao

MAPA_NOMES = {
    'BSBII': 'Promotoria de Justiça de Brasília II',
    'PJBZ': 'Promotoria de Justiça de Brazlândia',
    'PJCE': 'Promotoria de Justiça de Ceilândia',
    'PJGA': 'Promotoria de Justiça do Gama',
    'PJPA': 'Promotoria de Justiça do Paranoá',
    'PJPL': 'Promotoria de Justiça de Planaltina',
    'PJSA': 'Promotoria de Justiça de Samambaia',
    'PJSM': 'Promotoria de Justiça de Santa Maria',
    'PJSO': 'Promotoria de Justiça de Sobradinho',
    'PJSS': 'Promotoria de Justiça de São Sebastião',
    'PJTG': 'Promotoria de Justiça de Taguatinga e de Águas Claras',
}


class Command(BaseCommand):
    help = (
        'Renomeia edificações do painel de acessibilidade cujo nome ainda é '
        'a sigla (placeholder), para o nome por extenso da Promotoria.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Só mostra o que seria alterado, sem gravar no banco.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        alterados = 0
        for sigla, nome in MAPA_NOMES.items():
            obj = Edificacao.objects.filter(sigla=sigla).first()
            if obj is None:
                self.stdout.write(self.style.WARNING(f'Sigla não encontrada: {sigla}'))
                continue
            if obj.nome != obj.sigla:
                self.stdout.write(f'{sigla}: nome já definido ({obj.nome!r}) — pulando.')
                continue
            self.stdout.write(f'{sigla}: {obj.nome!r} -> {nome!r}')
            if not dry_run:
                obj.nome = nome
                obj.save(update_fields=['nome'])
            alterados += 1
        if dry_run:
            self.stdout.write(self.style.WARNING(f'[dry-run] {alterados} edificações seriam alteradas.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'{alterados} edificações renomeadas.'))
