from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0032_agreementsignature_witness_phone'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE vehicle_trackers
                ADD COLUMN IF NOT EXISTS payment_method varchar(30) NOT NULL DEFAULT 'cash';
            """,
            reverse_sql="""
                ALTER TABLE vehicle_trackers
                DROP COLUMN IF EXISTS payment_method;
            """,
            state_operations=[
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
            ],
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE vehicle_trackers
                ADD COLUMN IF NOT EXISTS installments_json text NOT NULL DEFAULT '[]';
            """,
            reverse_sql="""
                ALTER TABLE vehicle_trackers
                DROP COLUMN IF EXISTS installments_json;
            """,
            state_operations=[
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
            ],
        ),
    ]
