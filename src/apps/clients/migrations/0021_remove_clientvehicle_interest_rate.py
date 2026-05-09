# Generated migration to remove interest_rate field from ClientVehicle

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0004_remove_clientvehicle_salesperson_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='clientvehicle',
            name='interest_rate',
        ),
    ]
