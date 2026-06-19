from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0009_insuranceagentpayment'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE insurance_insurancepolicy
                ADD COLUMN IF NOT EXISTS insurance_payment_method varchar(30) NOT NULL DEFAULT 'cash';
            """,
            reverse_sql="""
                ALTER TABLE insurance_insurancepolicy
                DROP COLUMN IF EXISTS insurance_payment_method;
            """,
            state_operations=[
                migrations.AddField(
                    model_name='insurancepolicy',
                    name='insurance_payment_method',
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
                        help_text='Method used to pay for insurance',
                        max_length=30,
                        verbose_name='Payment Method',
                    ),
                ),
            ],
        ),
    ]
