# Generated migration to add transcript and thumbnail_storage_path fields to Clip

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clips', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='clip',
            name='transcript',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='clip',
            name='thumbnail_storage_path',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
