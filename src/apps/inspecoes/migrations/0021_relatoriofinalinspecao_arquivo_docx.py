import apps.inspecoes.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspecoes', '0020_inspecaoespecialidade_profissionais'),
    ]

    operations = [
        migrations.RenameField(
            model_name='relatoriofinalinspecao',
            old_name='arquivo_pdf',
            new_name='arquivo_docx',
        ),
        migrations.AlterField(
            model_name='relatoriofinalinspecao',
            name='arquivo_docx',
            field=models.FileField(upload_to=apps.inspecoes.models.relatorio_pdf_upload_path, verbose_name='Word gerado'),
        ),
    ]
