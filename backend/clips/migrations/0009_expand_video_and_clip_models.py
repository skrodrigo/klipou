# Generated migration for expanding Video and VideoClip models with R2 storage support

from django.db import migrations, models
import uuid


def fix_duplicate_clip_ids(apps, schema_editor):
    """Atribui UUIDs únicos para cada clip_id."""
    VideoClip = apps.get_model('clips', 'VideoClip')
    
    # Apenas atribui UUIDs únicos para cada clip
    for clip in VideoClip.objects.all():
        clip.clip_id = uuid.uuid4()
        clip.save()


class Migration(migrations.Migration):

    dependencies = [
        ('clips', '0008_recreate_thumbnail_field'),
    ]

    operations = [
        # Video model expansions
        migrations.AddField(
            model_name='video',
            name='video_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name='video',
            name='organization_id',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='user_id',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='source_type',
            field=models.CharField(
                choices=[('upload', 'Upload'), ('youtube', 'YouTube'), ('tiktok', 'TikTok'), ('instagram', 'Instagram'), ('url', 'URL')],
                default='upload',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='video',
            name='source_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='original_filename',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='storage_path',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='file_size',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='resolution',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='thumbnail_storage_path',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='current_step',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='last_successful_step',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='error_code',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='error_message',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='retry_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='video',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='version',
            field=models.IntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='video',
            name='status',
            field=models.CharField(
                choices=[
                    ('ingestion', 'Ingestion'),
                    ('queued', 'Queued'),
                    ('downloading', 'Downloading'),
                    ('normalizing', 'Normalizing'),
                    ('transcribing', 'Transcribing'),
                    ('analyzing', 'Analyzing'),
                    ('embedding', 'Embedding'),
                    ('selecting', 'Selecting'),
                    ('reframing', 'Reframing'),
                    ('clipping', 'Clipping'),
                    ('captioning', 'Captioning'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                ],
                default='ingestion',
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name='video',
            index=models.Index(fields=['organization_id', '-created_at'], name='clips_video_org_id_created_idx'),
        ),
        migrations.AddIndex(
            model_name='video',
            index=models.Index(fields=['status'], name='clips_video_status_idx'),
        ),
        migrations.AddIndex(
            model_name='video',
            index=models.Index(fields=['video_id'], name='clips_video_video_id_idx'),
        ),

        # VideoClip model expansions
        migrations.AddField(
            model_name='videoclip',
            name='clip_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
        migrations.AddField(
            model_name='videoclip',
            name='job_id',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='videoclip',
            name='duration',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='videoclip',
            name='ratio',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='videoclip',
            name='storage_path',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='videoclip',
            name='file_size',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='videoclip',
            name='engagement_score',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='videoclip',
            name='confidence_score',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='videoclip',
            name='version',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='videoclip',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddIndex(
            model_name='videoclip',
            index=models.Index(fields=['video_id', '-created_at'], name='clips_clip_video_created_idx'),
        ),
        migrations.AddIndex(
            model_name='videoclip',
            index=models.Index(fields=['clip_id'], name='clips_clip_clip_id_idx'),
        ),
        migrations.AddIndex(
            model_name='videoclip',
            index=models.Index(fields=['engagement_score'], name='clips_clip_engagement_idx'),
        ),
        # Limpa duplicatas após adicionar o campo
        migrations.RunPython(fix_duplicate_clip_ids, migrations.RunPython.noop),
    ]
