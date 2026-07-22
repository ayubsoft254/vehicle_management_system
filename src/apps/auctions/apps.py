from django.apps import AppConfig


class AuctionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.auctions'

    def ready(self):
        """Import signals when app is ready."""
        import apps.auctions.signals  # noqa: F401
