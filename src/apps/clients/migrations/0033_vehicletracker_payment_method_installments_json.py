from django.db import migrations, models


def add_tracker_columns_if_missing(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cols = {c.name for c in schema_editor.connection.introspection.get_table_description(cursor, 'vehicle_trackers')}
    VehicleTracker = apps.get_model('clients', 'VehicleTracker')
    if 'payment_method' not in cols:
        field = models.CharField(
            choices=[('cash','Cash'),('mpesa','M-Pesa'),('bank_transfer','Bank Transfer'),('cheque','Cheque'),('card','Credit/Debit Card'),('other','Other')],
            default='cash', max_length=30, verbose_name='Payment Method',
        )
        field.set_attributes_from_name('payment_method')
        schema_editor.add_field(VehicleTracker, field)
    if 'installments_json' not in cols:
        field = models.TextField(blank=True, default='[]', verbose_name='Installments Schedule (JSON)')
        field.set_attributes_from_name('installments_json')
        schema_editor.add_field(VehicleTracker, field)


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0032_agreementsignature_witness_phone'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='vehicletracker',
                    name='payment_method',
                    field=models.CharField(
                        choices=[('cash','Cash'),('mpesa','M-Pesa'),('bank_transfer','Bank Transfer'),('cheque','Cheque'),('card','Credit/Debit Card'),('other','Other')],
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
            ],
            database_operations=[
                migrations.RunPython(add_tracker_columns_if_missing, migrations.RunPython.noop),
            ],
        ),
    ]
