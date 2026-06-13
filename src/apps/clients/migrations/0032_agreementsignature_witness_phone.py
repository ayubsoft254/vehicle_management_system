from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0031_add_other_payment_details_to_clientvehicle'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE agreement_signatures
                ADD COLUMN IF NOT EXISTS witness_phone varchar(20) NOT NULL DEFAULT '';
            """,
            reverse_sql="""
                ALTER TABLE agreement_signatures
                DROP COLUMN IF EXISTS witness_phone;
            """,
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
        ),
    ]
