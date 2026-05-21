from django.db import migrations, models
import django.db.models.deletion
from django.db import transaction


def migrar_dados(apps, schema_editor):
    Inspecao = apps.get_model('inspecoes', 'Inspecao')
    InspecaoEspecialidade = apps.get_model('inspecoes', 'InspecaoEspecialidade')
    Achado = apps.get_model('inspecoes', 'Achado')

    # Mapeia edificacao_id -> pk do Inspecao container (o de menor pk)
    containers = {}
    for insp in Inspecao.objects.order_by('pk'):
        edif_id = insp.edificacao_id
        if edif_id not in containers:
            containers[edif_id] = insp.pk

    # Cria InspecaoEspecialidade para cada Inspecao existente
    # e registra o mapeamento: inspecao_pk_antigo -> especialidade_pk_novo
    mapa_insp_para_esp = {}
    for insp in Inspecao.objects.order_by('pk'):
        container_pk = containers[insp.edificacao_id]
        esp = InspecaoEspecialidade.objects.create(
            inspecao_id=container_pk,
            especialidade=insp.especialidade,
            profissional=insp.profissional,
            data_inspecao=insp.data_inspecao,
            status=insp.status,
        )
        mapa_insp_para_esp[insp.pk] = esp.pk

    # Atualiza cada Achado apontando para a nova InspecaoEspecialidade
    for achado in Achado.objects.all():
        achado.especialidade_id = mapa_insp_para_esp.get(achado.inspecao_id)
        achado.save(update_fields=['especialidade_id'])

    # Remove Inspecao objects que foram absorvidos (não são container)
    pks_para_deletar = [
        pk for pk in mapa_insp_para_esp
        if pk != containers.get(Inspecao.objects.get(pk=pk).edificacao_id)
    ]
    Inspecao.objects.filter(pk__in=pks_para_deletar).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inspecoes', '0003_achado_em_conformidade'),
    ]

    operations = [

        # 1. Cria a tabela InspecaoEspecialidade
        migrations.CreateModel(
            name='InspecaoEspecialidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('especialidade', models.CharField(
                    choices=[('civil', 'Engenharia Civil'), ('mecanica', 'Engenharia Mecânica'), ('eletrica', 'Engenharia Elétrica')],
                    max_length=20, verbose_name='Especialidade',
                )),
                ('profissional', models.CharField(max_length=200, verbose_name='Profissional responsável')),
                ('data_inspecao', models.DateField(verbose_name='Data da inspeção')),
                ('status', models.CharField(
                    choices=[('em_andamento', 'Em andamento'), ('finalizada', 'Finalizada')],
                    default='em_andamento', max_length=20, verbose_name='Status',
                )),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('inspecao', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='especialidades',
                    to='inspecoes.inspecao',
                    verbose_name='Inspeção',
                )),
            ],
            options={
                'verbose_name': 'Especialidade da Inspeção',
                'verbose_name_plural': 'Especialidades da Inspeção',
                'ordering': ['especialidade'],
            },
        ),

        # 2. Adiciona constraint de unicidade
        migrations.AddConstraint(
            model_name='inspecaoespecialidade',
            constraint=models.UniqueConstraint(
                fields=['inspecao', 'especialidade'],
                name='unique_inspecao_especialidade',
            ),
        ),

        # 3. Adiciona FK nullable em Achado → InspecaoEspecialidade
        migrations.AddField(
            model_name='achado',
            name='especialidade',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='achados',
                to='inspecoes.inspecaoespecialidade',
                verbose_name='Especialidade',
            ),
        ),

        # 4. Migração de dados
        migrations.RunPython(migrar_dados, migrations.RunPython.noop),

        # 5. Torna a FK obrigatória
        migrations.AlterField(
            model_name='achado',
            name='especialidade',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='achados',
                to='inspecoes.inspecaoespecialidade',
                verbose_name='Especialidade',
            ),
        ),

        # 6. Remove a FK antiga de Achado → Inspecao
        migrations.RemoveField(model_name='achado', name='inspecao'),

        # 7. Remove campos obsoletos de Inspecao
        migrations.RemoveField(model_name='inspecao', name='profissional'),
        migrations.RemoveField(model_name='inspecao', name='especialidade'),
        migrations.RemoveField(model_name='inspecao', name='data_inspecao'),
        migrations.RemoveField(model_name='inspecao', name='status'),
    ]
