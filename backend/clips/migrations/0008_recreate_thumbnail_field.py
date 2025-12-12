# Migration to properly recreate thumbnail field as TextField

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clips', '0007_alter_video_thumbnail_remove_thumbnail_base64'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='video',
            name='thumbnail',
        ),
        migrations.AddField(
            model_name='video',
            name='thumbnail',
            field=models.TextField(blank=True, null=True),
        ),
    ]
