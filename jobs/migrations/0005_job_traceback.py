# Generated by Django 3.1.8 on 2021-08-23 01:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0004_auto_20210322_2029'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='traceback',
            field=models.TextField(blank=True, null=True, verbose_name='traceback'),
        ),
    ]