from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reports'

    def ready(self):
        """Import signals when app is ready."""
        import apps.reports.signals  # noqa: F401
