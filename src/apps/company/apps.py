from django.apps import AppConfig


class CompanyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.company'
    verbose_name = 'Company & Branding'

    def ready(self):
        from django.db.models.signals import post_save

        from .models import CompanyProfile
        from .services import clear_company_cache

        post_save.connect(lambda **kwargs: clear_company_cache(), sender=CompanyProfile,
                          weak=False, dispatch_uid='company_profile_clear_cache')
