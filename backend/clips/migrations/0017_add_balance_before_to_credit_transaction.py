# Generated migration to add balance_before field to CreditTransaction

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clips', '0015_add_embedding_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='credittransaction',
            name='balance_before',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
