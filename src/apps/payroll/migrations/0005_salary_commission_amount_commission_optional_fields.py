from django.db import migrations, models
import django.core.validators
from decimal import Decimal


def rename_commission_rate_if_needed(apps, schema_editor):
    """
    Rename commission_rate → commission_amount on payroll_salarystructure,
    but only if the old column still exists. Databases initialised from the
    already-renamed model state will have commission_amount from the start
    and should skip the rename.
    """
    connection = schema_editor.connection
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(payroll_salarystructure)")
            has_old_column = any(row[1] == 'commission_rate' for row in cursor.fetchall())
    else:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = 'payroll_salarystructure'
                  AND column_name = 'commission_rate'
            """)
            has_old_column = cursor.fetchone()[0] > 0

    if has_old_column:
        with connection.cursor() as cursor:
            cursor.execute("""
                ALTER TABLE payroll_salarystructure
                RENAME COLUMN commission_rate TO commission_amount
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0004_employee_department_blank_hire_date_nullable'),
    ]

    operations = [
        # Use SeparateDatabaseAndState so the DB rename is conditional while
        # Django's migration state is always updated to reflect the new name.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    rename_commission_rate_if_needed,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.RenameField(
                    model_name='salarystructure',
                    old_name='commission_rate',
                    new_name='commission_amount',
                ),
            ],
        ),
        # Widen the field now that it holds KES amounts, not a percentage.
        migrations.AlterField(
            model_name='salarystructure',
            name='commission_amount',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Monthly commission amount (KES)',
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal('0'))],
            ),
        ),
        # Make Commission.commission_rate and Commission.base_amount optional.
        migrations.AlterField(
            model_name='commission',
            name='commission_rate',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=Decimal('0.00'),
                max_digits=5,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0')),
                    django.core.validators.MaxValueValidator(Decimal('100')),
                ],
            ),
        ),
        migrations.AlterField(
            model_name='commission',
            name='base_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Amount commission is calculated from',
                max_digits=10,
                null=True,
            ),
        ),
    ]
