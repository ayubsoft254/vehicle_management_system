from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0030_backfill_agreement_signature_party_columns'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE client_vehicles ADD COLUMN IF NOT EXISTS other_payment_details text;",
            reverse_sql=migrations.RunSQL.noop,
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
        ),
    ]
