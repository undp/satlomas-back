# Generated by Django 3.0.5 on 2020-04-28 02:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vi_lomas_changes', '0007_changesmask_mask'),
    ]

    operations = [
        migrations.AddField(
            model_name='coveragemeasurement',
            name='changes_mask',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='vi_lomas_changes.ChangesMask'),
        ),
    ]
