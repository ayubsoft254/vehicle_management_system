from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0003_employee_dob_nullable'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employee',
            name='department',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='employee',
            name='hire_date',
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='employee',
            name='national_id',
            field=models.CharField(max_length=50, unique=True, null=True, blank=True),
        ),
    ]
