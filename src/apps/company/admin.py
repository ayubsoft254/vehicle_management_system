from django.contrib import admin

from .models import CompanyProfile


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ('legal_name', 'country', 'currency_code', 'updated_at')
    # Secrets are encrypted in `mpesa`; edit them from Settings → Company & Branding.
    exclude = ('mpesa',)
    readonly_fields = ('version', 'updated_by', 'updated_at')

    def has_add_permission(self, request):
        return not CompanyProfile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
