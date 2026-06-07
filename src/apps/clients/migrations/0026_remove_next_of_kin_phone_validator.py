from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0025_clientvehicle_pricing_adjustments'),
    ]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='next_of_kin_phone',
            field=models.CharField(blank=True, max_length=20, verbose_name='Next of Kin Phone'),
        ),
    ]
