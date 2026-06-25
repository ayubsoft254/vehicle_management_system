from django.db import migrations, models


def add_witness_phone_if_missing(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cols = {c.name for c in schema_editor.connection.introspection.get_table_description(cursor, 'agreement_signatures')}
    if 'witness_phone' not in cols:
        AgreementSignature = apps.get_model('clients', 'AgreementSignature')
        field = models.CharField(blank=True, default='', max_length=20, verbose_name='Witness Phone / Mobile')
        field.set_attributes_from_name('witness_phone')
        schema_editor.add_field(AgreementSignature, field)


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0031_add_other_payment_details_to_clientvehicle'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
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
            ],
            database_operations=[
                migrations.RunPython(add_witness_phone_if_missing, migrations.RunPython.noop),
            ],
        ),
    ]
