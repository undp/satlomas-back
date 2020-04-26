# Generated by Django 3.0.5 on 2020-04-26 20:02

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('vi_lomas_changes', '0003_auto_20200425_2215'),
    ]

    operations = [
        migrations.AddField(
            model_name='coveragemeasurement',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='coveragemeasurement',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
