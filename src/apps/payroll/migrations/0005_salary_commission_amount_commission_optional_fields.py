from django.db import migrations, models
import django.core.validators
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0004_employee_department_blank_hire_date_nullable'),
    ]

    operations = [
        # Rename commission_rate → commission_amount on SalaryStructure and widen it
        migrations.RenameField(
            model_name='salarystructure',
            old_name='commission_rate',
            new_name='commission_amount',
        ),
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
        # Make Commission.commission_rate and Commission.base_amount optional
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
