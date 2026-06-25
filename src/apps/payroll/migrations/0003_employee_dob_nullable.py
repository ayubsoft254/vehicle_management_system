from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0002_employee_user_nullable'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employee',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
    ]
