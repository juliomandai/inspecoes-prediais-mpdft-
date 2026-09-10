from datetime import date, timedelta
from django.core.management.base import BaseCommand
from apps.inspecoes.models import Inspecao, Foto


class Command(BaseCommand):
    help = (
        'Remove DEFINITIVAMENTE (hard delete — não dá pra desfazer) inspeções '
        'criadas há mais de 180 dias, inclusive as já excluídas logicamente '
        '(soft delete). Retenção mínima exigida: 6 meses. Use --dry-run para '
        'pré-visualizar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas exibe o que seria removido, sem efetuar alterações.',
        )

    def handle(self, *args, **options):
        cutoff = date.today() - timedelta(days=180)
        # `todos_objects`: a purga de retenção tem que alcançar tanto as
        # inspeções ainda ativas quanto as já excluídas logicamente — soft
        # delete não é uma forma de escapar da purga, só um "desfazer" de
        # curto prazo.
        qs = Inspecao.todos_objects.filter(criado_em__date__lt=cutoff)
        count = qs.count()

        if options['dry_run']:
            self.stdout.write(
                f'[dry-run] {count} inspeção(ões) seriam removidas definitivamente '
                f'(criadas antes de {cutoff}).'
            )
            return

        fotos = Foto.todos_objects.filter(achado__especialidade__inspecao__in=qs)
        foto_count = fotos.count()
        for foto in fotos:
            if foto.arquivo:
                foto.arquivo.storage.delete(foto.arquivo.name)

        qs.apagar_definitivamente()
        self.stdout.write(self.style.SUCCESS(
            f'Removidas definitivamente: {count} inspeção(ões), {foto_count} foto(s).'
        ))
