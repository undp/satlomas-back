# Generated by Django 3.0.2 on 2020-01-27 15:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('measures', '0002_measure'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='measure',
            options={'managed': False},
        ),
        migrations.AddField(
            model_name='station',
            name='lat',
            field=models.DecimalField(decimal_places=6,
                                      max_digits=10,
                                      null=True),
        ),
        migrations.AddField(
            model_name='station',
            name='lon',
            field=models.DecimalField(decimal_places=6,
                                      max_digits=10,
                                      null=True),
        ),
        migrations.AlterField(
            model_name='station',
            name='name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='station',
            name='place_id',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='measures.Place'),
        ),
    ]