from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspecoes', '0008_visita_participantes'),
    ]

    operations = [
        migrations.AddField(
            model_name='visitatecnica',
            name='disciplina',
            field=models.CharField(
                'Disciplina', max_length=20, blank=True,
                choices=[
                    ('arquitetura', 'Arquitetura'),
                    ('civil', 'Engenharia Civil'),
                    ('eletrica', 'Engenharia Elétrica'),
                    ('mecanica', 'Engenharia Mecânica'),
                    ('multidisciplinar', 'Multidisciplinar'),
                ],
            ),
        ),
    ]
