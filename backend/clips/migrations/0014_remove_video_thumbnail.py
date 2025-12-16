# Generated migration to remove redundant thumbnail field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clips', '0013_clip_transcript_thumbnail'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='video',
            name='thumbnail',
        ),
    ]
