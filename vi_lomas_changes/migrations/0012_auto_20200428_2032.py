# Generated by Django 3.0.5 on 2020-04-28 20:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('vi_lomas_changes', '0011_auto_20200428_0256'),
    ]

    operations = [
        migrations.RenameField(
            model_name='coveragemeasurement',
            old_name='change_area',
            new_name='area',
        ),
        migrations.RenameField(
            model_name='coveragemeasurement',
            old_name='perc_change_area',
            new_name='perc_area',
        ),
        migrations.RemoveField(
            model_name='coveragemeasurement',
            name='changes_mask',
        ),
        migrations.DeleteModel(
            name='ChangesMask',
        ),
    ]