import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('stations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Measurement',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                # ('station_id',
                #  models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                #                    to='stations.Station')),
                ('station_id', models.IntegerField()),
                ('datetime', models.DateTimeField()),
                ('attributes',
                 django.contrib.postgres.fields.jsonb.JSONField(blank=True)),
            ],
        ),
        migrations.RunSQL([
            "ALTER TABLE stations_measurement DROP CONSTRAINT stations_measurement_pkey",
            "ALTER TABLE stations_measurement ADD PRIMARY KEY (datetime, station_id)",
            "SELECT create_hypertable('stations_measurement', 'datetime')"
        ])
    ]
