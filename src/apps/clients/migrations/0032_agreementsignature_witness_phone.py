from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0031_add_other_payment_details_to_clientvehicle'),
    ]

    operations = [
        migrations.AddField(
            model_name='agreementsignature',
            name='witness_phone',
            field=models.CharField(
                blank=True,
                help_text='Witness phone or mobile number',
                max_length=20,
                verbose_name='Witness Phone / Mobile',
            ),
        ),
    ]
