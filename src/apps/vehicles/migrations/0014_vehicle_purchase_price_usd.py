from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0013_agentpayments'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehicle',
            name='purchase_price_usd',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Purchase price in USD at time of acquisition',
                max_digits=12,
                null=True,
                verbose_name='Purchase Price (USD)',
            ),
        ),
        migrations.AddField(
            model_name='vehicle',
            name='purchase_usd_rate',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='KES/USD exchange rate recorded at time of purchase',
                max_digits=10,
                null=True,
                verbose_name='Exchange Rate at Purchase (KES per USD)',
            ),
        ),
    ]
