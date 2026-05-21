from django.apps import AppConfig


class InspecoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inspecoes'
    verbose_name = 'Inspeções'

    def ready(self):
        import apps.inspecoes.signals  # noqa: F401
