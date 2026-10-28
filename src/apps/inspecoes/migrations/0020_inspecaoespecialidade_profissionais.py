from django.db import migrations, models


def migrar_profissionais_para_entidade(apps, schema_editor):
    InspecaoEspecialidade = apps.get_model('inspecoes', 'InspecaoEspecialidade')
    Profissional = apps.get_model('edificacoes', 'Profissional')
    cache = {}
    contador = 1
    for esp in InspecaoEspecialidade.objects.all():
        nomes = [n.strip() for n in esp.profissional.splitlines() if n.strip()]
        for nome in nomes:
            chave = nome.lower()
            if chave not in cache:
                prof = Profissional.objects.filter(nome__iexact=nome).first()
                if prof is None:
                    prof = Profissional.objects.create(nome=nome, crea=f'PENDENTE-{contador}')
                    contador += 1
                cache[chave] = prof
            esp.profissionais.add(cache[chave])


def reverter_profissionais(apps, schema_editor):
    InspecaoEspecialidade = apps.get_model('inspecoes', 'InspecaoEspecialidade')
    for esp in InspecaoEspecialidade.objects.all():
        nomes = esp.profissionais.values_list('nome', flat=True)
        esp.profissional = '\n'.join(nomes)
        esp.save(update_fields=['profissional'])


class Migration(migrations.Migration):

    dependencies = [
        ('inspecoes', '0019_inspecaoespecialidade_numero_art'),
        ('edificacoes', '0006_profissional'),
    ]

    operations = [
        migrations.AddField(
            model_name='inspecaoespecialidade',
            name='profissionais',
            field=models.ManyToManyField(
                related_name='especialidades', to='edificacoes.profissional',
                verbose_name='Profissionais responsáveis',
            ),
        ),
        migrations.RunPython(migrar_profissionais_para_entidade, reverter_profissionais),
        migrations.RemoveField(
            model_name='inspecaoespecialidade',
            name='profissional',
        ),
    ]
