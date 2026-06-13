# Generated migration for TrackerAgentPayment and ClearingAgentPayment

import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0012_rename_trackerprovider_to_trackeragent'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TrackerAgentPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='Amount (KES)')),
                ('payment_date', models.DateField(default=django.utils.timezone.now, verbose_name='Payment Date')),
                ('payment_method', models.CharField(choices=[('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'), ('mpesa', 'M-Pesa'), ('cheque', 'Cheque'), ('other', 'Other')], default='bank_transfer', max_length=20, verbose_name='Payment Method')),
                ('reference_number', models.CharField(blank=True, max_length=100, verbose_name='Reference / Receipt No.')),
                ('notes', models.TextField(blank=True, verbose_name='Notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='vehicles.trackeragent')),
                ('recorded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tracker_agent_payments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Tracker Agent Payment',
                'verbose_name_plural': 'Tracker Agent Payments',
                'ordering': ['-payment_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ClearingAgentPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='Amount (KES)')),
                ('payment_date', models.DateField(default=django.utils.timezone.now, verbose_name='Payment Date')),
                ('payment_method', models.CharField(choices=[('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'), ('mpesa', 'M-Pesa'), ('cheque', 'Cheque'), ('other', 'Other')], default='bank_transfer', max_length=20, verbose_name='Payment Method')),
                ('reference_number', models.CharField(blank=True, max_length=100, verbose_name='Reference / Receipt No.')),
                ('notes', models.TextField(blank=True, verbose_name='Notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='vehicles.clearingagent')),
                ('recorded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clearing_agent_payments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Clearing Agent Payment',
                'verbose_name_plural': 'Clearing Agent Payments',
                'ordering': ['-payment_date', '-created_at'],
            },
        ),
    ]
