from datetime import date
from django.core.management.base import BaseCommand
from apps.edificacoes.models import Edificacao
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado


class Command(BaseCommand):
    help = 'Carrega dados de demonstração (operação idempotente).'

    def handle(self, *args, **options):
        edificacao, _ = Edificacao.objects.get_or_create(
            nome='Sede MPDFT — Bloco A',
            defaults={'endereco': 'SAAN Quadra 1 Lote 385, Brasília-DF', 'ativo': True},
        )

        inspecao, _ = Inspecao.objects.get_or_create(edificacao=edificacao)

        especialidade, created = InspecaoEspecialidade.objects.get_or_create(
            inspecao=inspecao,
            especialidade='civil',
            defaults={'profissional': 'Demo SPO', 'data_inspecao': date.today(), 'status': 'em_andamento'},
        )

        if created:
            Achado.objects.create(
                especialidade=especialidade,
                localizacao='Fachada Sul',
                verificacao='Presença de fissuras verticais',
                grupo_tecnico='estrutura',
                descricao_nao_conformidade='Fissuras verticais de até 3 mm observadas na fachada sul, com progressão aparente.',
                requisito_afetado='seguranca_estrutural',
                gravidade=5, urgencia=4, tendencia=3,
                prioridade_risco=1,
                recomendacao='Investigação estrutural imediata e reparo por profissional habilitado em engenharia estrutural.',
                direcionamento='nova_contratacao',
                prazo_meses=1,
            )
            Achado.objects.create(
                especialidade=especialidade,
                localizacao='Banheiro — 2º andar',
                verificacao='Torneira com vazamento contínuo',
                grupo_tecnico='instalacoes',
                descricao_nao_conformidade='Torneira da pia do banheiro masculino apresenta vazamento contínuo de água.',
                requisito_afetado='funcionalidade',
                gravidade=2, urgencia=2, tendencia=1,
                prioridade_risco=3,
                recomendacao='Substituição do retentor da torneira pela equipe de manutenção predial.',
                direcionamento='manutencao',
                prazo_meses=3,
            )
            self.stdout.write(self.style.SUCCESS('Achados de demonstração criados.'))
        else:
            self.stdout.write('Inspeção de demonstração já existia; nenhuma alteração feita.')

        self.stdout.write(self.style.SUCCESS(f'Edificação: "{edificacao.nome}"'))
        self.stdout.write(self.style.SUCCESS(
            f'Inspeção #{inspecao.pk}: {especialidade.profissional} — {especialidade.get_especialidade_display()}'
        ))
        self.stdout.write('')
        self.stdout.write('Acesse: http://127.0.0.1:8000/')
        self.stdout.write('Login com o superusuário criado via "python manage.py createsuperuser"')
