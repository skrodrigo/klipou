# Generated migration to add unique constraint on clip_id after cleaning duplicates

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clips', '0009_expand_video_and_clip_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='videoclip',
            name='clip_id',
            field=models.UUIDField(editable=False, unique=True),
        ),
    ]
