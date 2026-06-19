from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0032_agreementsignature_witness_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehicletracker',
            name='payment_method',
            field=models.CharField(
                choices=[
                    ('cash', 'Cash'),
                    ('mpesa', 'M-Pesa'),
                    ('bank_transfer', 'Bank Transfer'),
                    ('cheque', 'Cheque'),
                    ('card', 'Credit/Debit Card'),
                    ('other', 'Other'),
                ],
                default='cash',
                help_text='Method used to pay for this tracker',
                max_length=30,
                verbose_name='Payment Method',
            ),
        ),
        migrations.AddField(
            model_name='vehicletracker',
            name='installments_json',
            field=models.TextField(
                blank=True,
                default='[]',
                help_text='JSON array of {due_date, amount} installment schedule entries',
                verbose_name='Installments Schedule (JSON)',
            ),
        ),
    ]
