from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('DunnoRPG', '0147_delay_trip_mobility')]

    operations = [
        migrations.AddField(
            model_name='eq',
            name='book_trade_locked',
            field=models.BooleanField(default=False, editable=False),
        ),
    ]
