# Generated by Django 3.1.8 on 2021-08-28 13:34

import django.contrib.postgres.fields.hstore
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stations', '0017_hstore_extension'),
    ]

    operations = [
        migrations.AddField(
            model_name='site',
            name='attributes',
            field=django.contrib.postgres.fields.hstore.HStoreField(blank=True, null=True),
        ),
    ]