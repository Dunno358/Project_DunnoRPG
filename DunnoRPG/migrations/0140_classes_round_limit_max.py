from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0139_classes_counter_gaining_losing_limit'),
    ]

    operations = [
        migrations.RenameField(
            model_name='classes',
            old_name='limit',
            new_name='round_limit',
        ),
        migrations.AddField(
            model_name='classes',
            name='max',
            field=models.IntegerField(blank=True, help_text='Maksymalna wartość licznika.', null=True),
        ),
    ]
