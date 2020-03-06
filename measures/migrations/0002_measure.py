import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('measures', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Measure',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('station_id', models.TextField(blank=True, null=True)),
                ('datetime', models.DateTimeField()),
                ('attributes',
                 django.contrib.postgres.fields.jsonb.JSONField(blank=True,
                                                                null=True)),
            ],
        ),
        migrations.RunSQL([
            "ALTER TABLE measures_measure DROP CONSTRAINT measures_measure_pkey",
            "ALTER TABLE measures_measure ADD PRIMARY KEY (datetime, station_id)",
            "SELECT create_hypertable('measures_measure', 'datetime')"
        ])
    ]
