from django.db import migrations


def ensure_agreement_signature_party_columns(apps, schema_editor):
    AgreementSignature = apps.get_model('clients', 'AgreementSignature')
    table_name = AgreementSignature._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            column.name for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    for field_name in [
        'witness_name',
        'witness_id_number',
        'seller_name',
        'witness_signature_data',
        'seller_signature_data',
    ]:
        if field_name in existing_columns:
            continue
        schema_editor.add_field(AgreementSignature, AgreementSignature._meta.get_field(field_name))


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0029_agreement_signature_parties'),
    ]

    operations = [
        migrations.RunPython(
            ensure_agreement_signature_party_columns,
            migrations.RunPython.noop,
        ),
    ]