import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0035_vehicletracker_renewal_of'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='AgreementVersion',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('version_number', models.PositiveIntegerField()),
                        ('label', models.CharField(default='', help_text='Short description, e.g. "Original Signed Agreement" or "Revision 1"', max_length=200)),
                        ('snapshot', models.JSONField(help_text='Frozen vehicle/client/purchase/insurance/tracker data at version creation time')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('client_vehicle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='agreement_versions', to='clients.clientvehicle')),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='agreement_versions_created', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'verbose_name': 'Agreement Version',
                        'verbose_name_plural': 'Agreement Versions',
                        'db_table': 'agreement_versions',
                        'ordering': ['version_number'],
                        'unique_together': {('client_vehicle', 'version_number')},
                    },
                ),
            ],
        ),
    ]
