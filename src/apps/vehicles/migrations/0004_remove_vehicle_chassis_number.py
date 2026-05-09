# Generated migration to remove chassis_number field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0003_vehicle_ship_name_vehicle_vessel_number'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='vehicle',
            name='chassis_number',
        ),
    ]
