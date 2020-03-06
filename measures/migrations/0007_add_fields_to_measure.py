from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('measures', '0006_rename_fks'),
    ]

    operations = [
        migrations.AddField(
            model_name='measure',
            name='wind_speed',
            field=models.DecimalField(decimal_places=6,
                                      max_digits=10,
                                      blank=True,
                                      null=True),
        ),
        migrations.AddField(
            model_name='measure',
            name='wind_direction',
            field=models.DecimalField(decimal_places=6,
                                      max_digits=10,
                                      blank=True,
                                      null=True),
        ),
        migrations.AddField(
            model_name='measure',
            name='pressure',
            field=models.DecimalField(decimal_places=6,
                                      max_digits=10,
                                      blank=True,
                                      null=True),
        ),
        migrations.AddField(
            model_name='measure',
            name='precipitation',
            field=models.DecimalField(decimal_places=6,
                                      max_digits=10,
                                      blank=True,
                                      null=True),
        ),
        migrations.AddField(
            model_name='measure',
            name='pm25',
            field=models.DecimalField(decimal_places=6,
                                      max_digits=10,
                                      blank=True,
                                      null=True),
        ),
    ]
