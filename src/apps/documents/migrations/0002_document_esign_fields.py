from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='esign_provider',
            field=models.CharField(blank=True, help_text='E-signature provider used for this document (e.g., docuseal)', max_length=30),
        ),
        migrations.AddField(
            model_name='document',
            name='esign_requested_at',
            field=models.DateTimeField(blank=True, help_text='When the latest e-signature request was created', null=True),
        ),
        migrations.AddField(
            model_name='document',
            name='esign_signer_email',
            field=models.EmailField(blank=True, help_text='Requested signer email', max_length=254),
        ),
        migrations.AddField(
            model_name='document',
            name='esign_signer_name',
            field=models.CharField(blank=True, help_text='Requested signer name', max_length=255),
        ),
        migrations.AddField(
            model_name='document',
            name='esign_signing_link',
            field=models.URLField(blank=True, help_text='Direct signing URL returned by provider'),
        ),
        migrations.AddField(
            model_name='document',
            name='esign_status',
            field=models.CharField(blank=True, help_text='Current e-signature status (pending/completed/failed)', max_length=20),
        ),
        migrations.AddField(
            model_name='document',
            name='esign_submission_id',
            field=models.CharField(blank=True, help_text='Provider submission identifier', max_length=100),
        ),
    ]
