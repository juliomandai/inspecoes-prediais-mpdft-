from datetime import date, timedelta
from django.core.management.base import BaseCommand
from apps.inspecoes.models import Inspecao, Foto


class Command(BaseCommand):
    help = 'Remove inspeções com data anterior a 180 dias. Use --dry-run para pré-visualizar.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas exibe o que seria removido, sem efetuar alterações.',
        )

    def handle(self, *args, **options):
        cutoff = date.today() - timedelta(days=180)
        qs = Inspecao.objects.filter(data_inspecao__lt=cutoff)
        count = qs.count()

        if options['dry_run']:
            self.stdout.write(
                f'[dry-run] {count} inspeção(ões) seriam removidas (data anterior a {cutoff}).'
            )
            return

        fotos = Foto.objects.filter(achado__inspecao__in=qs)
        foto_count = fotos.count()
        for foto in fotos:
            if foto.arquivo:
                foto.arquivo.storage.delete(foto.arquivo.name)

        qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'Removidas: {count} inspeção(ões), {foto_count} foto(s).'
        ))
