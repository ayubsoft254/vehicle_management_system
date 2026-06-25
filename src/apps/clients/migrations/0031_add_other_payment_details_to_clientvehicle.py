from django.db import migrations, models


def add_column_if_missing(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cols = {c.name for c in schema_editor.connection.introspection.get_table_description(cursor, 'client_vehicles')}
    if 'other_payment_details' not in cols:
        ClientVehicle = apps.get_model('clients', 'ClientVehicle')
        field = models.TextField(blank=True, help_text='Optional payment details to include in the agreement', verbose_name='Other Payment Details')
        field.set_attributes_from_name('other_payment_details')
        schema_editor.add_field(ClientVehicle, field)


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0030_backfill_agreement_signature_party_columns'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='clientvehicle',
                    name='other_payment_details',
                    field=models.TextField(
                        blank=True,
                        help_text='Optional payment details to include in the agreement',
                        verbose_name='Other Payment Details'
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_column_if_missing, migrations.RunPython.noop),
            ],
        ),
    ]
