from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0130_rename_wschodnie_ziemie_chapter'),
    ]

    operations = [
        migrations.AddField(
            model_name='character',
            name='advantageBalance',
            field=models.IntegerField(default=0),
        ),
    ]
