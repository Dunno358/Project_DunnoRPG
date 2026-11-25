from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('DunnoRPG', '0148_eq_book_trade_locked')]

    operations = [
        migrations.AddField(
            model_name='character',
            name='fight_damage_dealt',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
