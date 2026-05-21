from django.db import migrations, models

LOCALIZACOES_PADRAO = [
    '1º pavimento',
    '2º pavimento',
    'Área externa',
    'Cobertura',
    'Escadas',
    'Fachada',
    'Geral',
    'Subsolo',
    'Térreo',
]


def criar_localizacoes_padrao(apps, schema_editor):
    OpcaoCampo = apps.get_model('inspecoes', 'OpcaoCampo')
    for i, label in enumerate(LOCALIZACOES_PADRAO):
        OpcaoCampo.objects.create(
            campo='localizacao',
            label=label,
            is_padrao=True,
            ordem=i,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('inspecoes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OpcaoCampo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('campo', models.CharField(
                    choices=[
                        ('localizacao', 'Localização'),
                        ('grupo_tecnico', 'Grupo técnico'),
                        ('requisito_afetado', 'Requisito afetado'),
                    ],
                    max_length=30,
                    verbose_name='Campo',
                )),
                ('label', models.CharField(max_length=200, verbose_name='Descrição')),
                ('is_padrao', models.BooleanField(default=False, verbose_name='Padrão do sistema')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                ('ordem', models.PositiveIntegerField(default=0, verbose_name='Ordem')),
            ],
            options={
                'verbose_name': 'Opção de campo',
                'verbose_name_plural': 'Opções de campos',
                'ordering': ['campo', 'ordem', 'label'],
            },
        ),
        migrations.AddConstraint(
            model_name='opcaocampo',
            constraint=models.UniqueConstraint(
                fields=['campo', 'label'],
                name='unique_campo_label',
            ),
        ),
        migrations.RunPython(criar_localizacoes_padrao, migrations.RunPython.noop),
    ]
