"""Corrige a duplicidade de edificações criada pela importação do painel de
acessibilidade: o comando `importar_painel_acessibilidade` usa
`Edificacao.objects.get_or_create(sigla=sigla, defaults={'nome': sigla})`, e
em bancos onde a edificação já existia (cadastrada antes pelo módulo de
Visitas Técnicas / Inspeções, normalmente sem `sigla` preenchida) isso cria
uma SEGUNDA linha "placeholder" (nome igual à sigla) em vez de reaproveitar
a linha já existente.

Este comando funde cada linha placeholder na linha "oficial" já existente
(quando encontrada) — reatribuindo `LocalAcessibilidade`, `Inspecao` e
`VisitaTecnica` para a edificação oficial, copiando a sigla para ela e
apagando a linha placeholder. Quando NÃO existe uma linha oficial
correspondente (ex.: banco de dev, ou uma Promotoria que só existe no
painel de acessibilidade), o placeholder é apenas renomeado no lugar.

O Edifício-sede (BSBI) é um caso especial: as duas alas (Bloco A e Bloco B)
compartilham a mesma sigla no painel de acessibilidade, então a linha oficial
fica só como "Edifício-sede" (sem distinguir bloco) após a fusão.

Idempotente — rodar de novo não tem efeito colateral (a linha placeholder
já não existirá mais).

Uso:
    python manage.py renomear_edificacoes_acessibilidade
    python manage.py renomear_edificacoes_acessibilidade --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import LocalAcessibilidade
from apps.inspecoes.models import Inspecao, VisitaTecnica

# sigla do placeholder -> critério para achar a edificação oficial já
# existente. Usamos `nome` exato quando não há ambiguidade de acentuação/
# hífen, e uma busca por trecho (`contains`) para o caso do Edifício-sede,
# cujo nome pode ter sido digitado com hífen ou travessão.
MAPA_MERGE = {
    'BSBI': {'contains': 'Bloco A', 'renomear_oficial_para': 'Edifício-sede'},
    'BSBII': {'nome': 'Promotoria de Justiça de Brasília II'},
    'PJBZ': {'nome': 'Promotoria de Justiça de Brazlândia'},
    'PJCE': {'nome': 'Promotoria de Justiça de Ceilândia'},
    'PJGA': {'nome': 'Promotoria de Justiça do Gama'},
    'PJPA': {'nome': 'Promotoria de Justiça do Paranoá'},
    'PJPL': {'nome': 'Promotoria de Justiça de Planaltina'},
    'PJSA': {'nome': 'Promotoria de Justiça de Samambaia'},
    'PJSM': {'nome': 'Promotoria de Justiça de Santa Maria'},
    'PJSO': {'nome': 'Promotoria de Justiça de Sobradinho'},
    'PJSS': {'nome': 'Promotoria de Justiça de São Sebastião'},
    'PJTG': {'nome': 'Promotoria de Justiça de Taguatinga e de Águas Claras'},
}


class Command(BaseCommand):
    help = (
        'Funde as edificações-placeholder criadas pela importação do painel '
        'de acessibilidade nas edificações oficiais já cadastradas (quando '
        'existirem), ou as renomeia no lugar quando não há duplicidade.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Só mostra o que seria feito, sem gravar no banco.',
        )

    def _achar_oficial(self, placeholder, criterio):
        qs = Edificacao.objects.exclude(pk=placeholder.pk)
        if 'nome' in criterio:
            return qs.filter(nome=criterio['nome']).first()
        return qs.filter(Q(sigla__isnull=True) & Q(nome__icontains=criterio['contains'])).first()

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        for sigla, criterio in MAPA_MERGE.items():
            placeholder = Edificacao.objects.filter(sigla=sigla, nome=sigla).first()
            if placeholder is None:
                continue  # já foi processado antes, ou nunca existiu como placeholder

            oficial = self._achar_oficial(placeholder, criterio)
            nome_alvo = criterio.get('nome', placeholder.nome)

            if oficial is None:
                self.stdout.write(f'{sigla}: sem duplicata — renomeando no lugar para {nome_alvo!r}.')
                if not dry_run:
                    placeholder.nome = nome_alvo
                    placeholder.save(update_fields=['nome'])
                continue

            self.stdout.write(
                f'{sigla}: fundindo placeholder (id={placeholder.pk}) em '
                f'{oficial.nome!r} (id={oficial.pk}).'
            )
            if dry_run:
                continue

            LocalAcessibilidade.objects.filter(edificacao=placeholder).update(edificacao=oficial)
            Inspecao.objects.filter(edificacao=placeholder).update(edificacao=oficial)
            VisitaTecnica.objects.filter(edificacao=placeholder).update(edificacao=oficial)

            # apaga o placeholder antes de copiar a sigla para a oficial —
            # a coluna `sigla` é única, então as duas não podem carregar o
            # mesmo valor ao mesmo tempo.
            # Fusão de duplicata é limpeza de dados, não exclusão de usuário —
            # remove de verdade (apagar_definitivamente); senão o placeholder
            # ficaria "excluído" mas continuaria existindo, mesmo que a
            # constraint de unicidade (agora condicional a excluido_em)
            # deixe de bloquear a sigla/nome.
            placeholder.apagar_definitivamente()

            update_fields = []
            if not oficial.sigla:
                oficial.sigla = sigla
                update_fields.append('sigla')
            nome_oficial_final = criterio.get('renomear_oficial_para')
            if nome_oficial_final and oficial.nome != nome_oficial_final:
                oficial.nome = nome_oficial_final
                update_fields.append('nome')
            if update_fields:
                oficial.save(update_fields=update_fields)

        # Caso a fusão já tenha rodado numa execução anterior (placeholder já
        # apagado), garante que a renomeação final da oficial ainda é aplicada.
        for sigla, criterio in MAPA_MERGE.items():
            nome_final = criterio.get('renomear_oficial_para')
            if not nome_final:
                continue
            oficial = Edificacao.objects.filter(sigla=sigla).exclude(nome=nome_final).first()
            if oficial is None:
                continue
            self.stdout.write(f'{sigla}: renomeando {oficial.nome!r} -> {nome_final!r}.')
            if not dry_run:
                oficial.nome = nome_final
                oficial.save(update_fields=['nome'])

        if dry_run:
            self.stdout.write(self.style.WARNING('[dry-run] nenhuma alteração foi gravada.'))
        else:
            self.stdout.write(self.style.SUCCESS('Concluído.'))
