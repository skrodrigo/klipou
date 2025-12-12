# Generated migration to change thumbnail field to TextField and remove thumbnail_base64

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clips', '0006_video_thumbnail_base64'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='video',
            name='thumbnail_base64',
        ),
        migrations.AlterField(
            model_name='video',
            name='thumbnail',
            field=models.TextField(blank=True, null=True),
        ),
    ]
