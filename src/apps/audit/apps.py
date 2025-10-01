from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.audit'

    def ready(self):
        """
        Import signal handlers when app is ready
        Signals are used to track login/logout events
        """
        # Import signals to register them
        # The middleware.py contains signal receivers for login/logout
        import apps.audit.middleware
