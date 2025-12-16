from django.contrib.postgres.fields import ArrayField
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('clips', '0014_remove_video_thumbnail'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmbeddingPattern',
            fields=[
                ('pattern_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('category', models.CharField(choices=[('engagement', 'High Engagement'), ('viral', 'Viral Content'), ('educational', 'Educational'), ('entertainment', 'Entertainment')], max_length=50)),
                ('embedding', ArrayField(models.FloatField())),
                ('embedding_dimension', models.IntegerField(default=768)),
                ('embedding_model', models.CharField(default='gemini-embedding-004', max_length=100)),
                ('description', models.TextField(blank=True)),
                ('sample_count', models.IntegerField(default=0)),
                ('confidence_score', models.FloatField(default=0.5)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='embedding_patterns', to='clips.organization')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['organization', 'category'], name='clips_embe_organiz_idx'),
                    models.Index(fields=['organization'], name='clips_embe_organiz_2_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='EmbeddingCache',
            fields=[
                ('cache_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('text_hash', models.CharField(db_index=True, max_length=64, unique=True)),
                ('text_content', models.TextField()),
                ('embedding', ArrayField(models.FloatField())),
                ('embedding_dimension', models.IntegerField(default=768)),
                ('embedding_model', models.CharField(default='gemini-embedding-004', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_accessed', models.DateTimeField(auto_now=True)),
                ('access_count', models.IntegerField(default=0)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['text_hash'], name='clips_embe_text_ha_idx'),
                    models.Index(fields=['last_accessed'], name='clips_embe_last_ac_idx'),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name='embeddingpattern',
            constraint=models.UniqueConstraint(fields=['organization', 'name'], name='unique_org_pattern_name'),
        ),
    ]
