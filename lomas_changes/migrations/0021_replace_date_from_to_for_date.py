# Generated by Django 3.0.10 on 2020-11-08 16:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scopes', '0002_auto_20200428_2233'),
        ('lomas_changes', '0020_delete_unused_models'),
    ]

    operations = [
        migrations.RenameField(
            model_name='coveragemeasurement',
            old_name='date_from',
            new_name='date',
        ),
        migrations.AlterUniqueTogether(
            name='coveragemeasurement',
            unique_together={('date', 'scope')},
        ),
        migrations.RemoveField(
            model_name='coveragemeasurement',
            name='date_to',
        ),
    ]
