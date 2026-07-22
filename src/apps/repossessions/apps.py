from django.apps import AppConfig


class RepossessionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.repossessions'

    def ready(self):
        """Import signals when app is ready."""
        import apps.repossessions.signals  # noqa: F401
