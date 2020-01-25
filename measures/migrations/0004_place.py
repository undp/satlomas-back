# Generated by Django 3.0.2 on 2020-01-25 13:43

import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('measures', '0003_add_missing_fields_to_device'),
    ]

    operations = [
        migrations.CreateModel(
            name='Place',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('geom',
                 django.contrib.gis.db.models.fields.PolygonField(srid=4326)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('parent_id',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                   to='measures.Place')),
            ],
        ),
    ]
