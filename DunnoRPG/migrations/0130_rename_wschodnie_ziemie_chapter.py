from django.db import migrations


def rename_chapter(apps, schema_editor):
    GameSettings = apps.get_model('DunnoRPG', 'GameSettings')
    Images = apps.get_model('DunnoRPG', 'Images')

    GameSettings.objects.filter(current_chapter='Wschodnie Ziemie').update(current_chapter='Wschód')
    Images.objects.filter(chapter='Wschodnie Ziemie').update(chapter='Wschód')


def restore_chapter(apps, schema_editor):
    GameSettings = apps.get_model('DunnoRPG', 'GameSettings')
    Images = apps.get_model('DunnoRPG', 'Images')

    GameSettings.objects.filter(current_chapter='Wschód').update(current_chapter='Wschodnie Ziemie')
    Images.objects.filter(chapter='Wschód').update(chapter='Wschodnie Ziemie')


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0129_alter_images_visible'),
    ]

    operations = [
        migrations.RunPython(rename_chapter, restore_chapter),
    ]
