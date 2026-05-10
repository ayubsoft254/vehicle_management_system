# Generated migration to add ship_name and vessel_number fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0002_vehicle_clearance_cost_vehicle_commission_cost_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehicle',
            name='ship_name',
            field=models.CharField(blank=True, help_text='Name of the vessel/ship used for transport', max_length=200, null=True, verbose_name='Ship Name'),
        ),
        migrations.AddField(
            model_name='vehicle',
            name='vessel_number',
            field=models.CharField(blank=True, help_text='Vessel identification number or code', max_length=100, null=True, verbose_name='Vessel Number'),
        ),
    ]
