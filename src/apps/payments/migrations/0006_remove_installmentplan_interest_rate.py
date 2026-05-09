# Generated migration to remove interest_rate field from InstallmentPlan

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_paymentschedule_late_fee_applied'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='installmentplan',
            name='interest_rate',
        ),
    ]
