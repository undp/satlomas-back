# Generated by Django 3.0.10 on 2020-10-20 20:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0002_auto_20200924_1800'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='queue',
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name='queue'),
        ),
    ]
