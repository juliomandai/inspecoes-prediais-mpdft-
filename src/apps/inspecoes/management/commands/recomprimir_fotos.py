"""Recomprime o acervo de fotos já existente.

Percorre todas as fotos de achados e de visitas técnicas, recomprime cada
imagem com os mesmos parâmetros usados no upload (reorientação EXIF,
redimensionamento e JPEG otimizado) e substitui o arquivo antigo pelo novo,
atualizando o tamanho registrado no banco.

Uso:
    python manage.py recomprimir_fotos            # aplica de fato
    python manage.py recomprimir_fotos --dry-run  # só simula e relata
"""
import os

from django.core.management.base import BaseCommand

from apps.inspecoes.models import Foto, VisitaFoto
from apps.inspecoes.imagens import comprimir_imagem


class Command(BaseCommand):
    help = 'Recomprime/otimiza todas as fotos já armazenadas (achados e visitas).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Apenas simula e mostra a economia estimada, sem alterar arquivos.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        if dry:
            self.stdout.write(self.style.WARNING('MODO SIMULAÇÃO (--dry-run): nada será alterado.\n'))

        total_antes = 0
        total_depois = 0
        processadas = 0
        puladas = 0
        falhas = 0

        for modelo, rotulo in ((Foto, 'achado'), (VisitaFoto, 'visita')):
            for foto in modelo.objects.all().iterator():
                campo = foto.arquivo
                if not campo:
                    continue
                try:
                    caminho_antigo = campo.path
                except Exception:
                    caminho_antigo = None

                try:
                    campo.open('rb')
                    dados = campo.read()
                    campo.close()
                except Exception as e:
                    falhas += 1
                    self.stderr.write(self.style.ERROR(
                        f'[{rotulo} #{foto.pk}] não foi possível ler o arquivo: {e}'))
                    continue

                tam_antes = len(dados)
                cf, nome, tam_depois = comprimir_imagem(dados, foto.nome_original or os.path.basename(campo.name))

                # Só vale a pena substituir se realmente ficou menor.
                if tam_depois >= tam_antes:
                    puladas += 1
                    total_antes += tam_antes
                    total_depois += tam_antes
                    continue

                total_antes += tam_antes
                total_depois += tam_depois
                processadas += 1

                economia = (1 - tam_depois / tam_antes) * 100
                self.stdout.write(
                    f'[{rotulo} #{foto.pk}] {tam_antes // 1024} KB -> '
                    f'{tam_depois // 1024} KB  (-{economia:.0f}%)'
                )

                if dry:
                    continue

                # Grava o novo arquivo, atualiza o registro e remove o antigo.
                novo_basename = os.path.basename(campo.name)
                base, _ = os.path.splitext(novo_basename)
                cf.name = f'{base}.jpg'

                nome_antigo_storage = campo.name
                foto.arquivo.save(cf.name, cf, save=False)
                foto.tamanho_bytes = tam_depois
                foto.save(update_fields=['arquivo', 'tamanho_bytes'])

                # Remove o arquivo original se o caminho mudou.
                if caminho_antigo and foto.arquivo.name != nome_antigo_storage:
                    try:
                        if os.path.exists(caminho_antigo):
                            os.remove(caminho_antigo)
                    except Exception:
                        pass

        mb = 1024 * 1024
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Concluído. Processadas: {processadas} | já otimizadas: {puladas} | falhas: {falhas}'))
        self.stdout.write(self.style.SUCCESS(
            f'Tamanho total: {total_antes / mb:.1f} MB -> {total_depois / mb:.1f} MB '
            f'(economia de {(total_antes - total_depois) / mb:.1f} MB)'))
        if dry:
            self.stdout.write(self.style.WARNING(
                '\nNada foi alterado (simulação). Rode sem --dry-run para aplicar.'))
