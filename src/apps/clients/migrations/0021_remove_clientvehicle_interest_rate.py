# Generated migration to remove interest_rate field from ClientVehicle

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0002_vehicletracker_interest_rate'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='clientvehicle',
            name='interest_rate',
        ),
    ]
