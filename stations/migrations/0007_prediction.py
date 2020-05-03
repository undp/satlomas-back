import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('stations', '0006_rename_fks'),
    ]

    operations = [
        migrations.CreateModel(
            name='Prediction',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('station_id', models.IntegerField()),
                ('datetime', models.DateTimeField()),
                ('attributes',
                 django.contrib.postgres.fields.jsonb.JSONField(blank=True)),
            ],
        ),
        migrations.RunSQL([
            "ALTER TABLE stations_prediction DROP CONSTRAINT stations_prediction_pkey",
            "ALTER TABLE stations_prediction ADD PRIMARY KEY (datetime, station_id)",
            "SELECT create_hypertable('stations_prediction', 'datetime')"
        ])
    ]
