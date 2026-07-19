from django.apps import AppConfig


class ExpensesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.expenses'

    def ready(self):
        """Import signals when app is ready"""
        import apps.expenses.signals
