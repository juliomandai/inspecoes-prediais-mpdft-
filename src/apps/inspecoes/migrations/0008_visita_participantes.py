from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspecoes', '0007_alter_logacesso_tipo_visitatecnica_visitafoto'),
    ]

    operations = [
        migrations.RenameField(
            model_name='visitatecnica',
            old_name='responsavel',
            new_name='participantes',
        ),
        migrations.AlterField(
            model_name='visitatecnica',
            name='participantes',
            field=models.TextField('Profissionais participantes', help_text='Um nome por linha.'),
        ),
    ]
