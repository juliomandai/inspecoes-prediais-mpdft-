from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from .models import Foto


@receiver(post_delete, sender=Foto)
def foto_delete_arquivo(sender, instance, **kwargs):
    if instance.arquivo:
        instance.arquivo.storage.delete(instance.arquivo.name)


@receiver(user_logged_in)
def registrar_login(sender, request, user, **kwargs):
    from .models import LogAcesso
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR')
    )
    nome = user.get_full_name() or user.username
    LogAcesso.objects.create(
        usuario=user,
        tipo='login',
        descricao=f'Login realizado por {nome}.',
        ip=ip or None,
    )
