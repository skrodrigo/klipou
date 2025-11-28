from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clips", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Video",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name="videoclip",
            name="video",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, related_name="clips", to="clips.video"),
        ),
    ]
