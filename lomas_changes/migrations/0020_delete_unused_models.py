# Generated by Django 3.0.10 on 2020-11-08 15:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lomas_changes', '0019_replace_raster_period_for_date'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='object',
            name='period',
        ),
        migrations.AlterUniqueTogether(
            name='period',
            unique_together=None,
        ),
        migrations.DeleteModel(
            name='Mask',
        ),
        migrations.DeleteModel(
            name='Object',
        ),
        migrations.DeleteModel(
            name='Period',
        ),
    ]
