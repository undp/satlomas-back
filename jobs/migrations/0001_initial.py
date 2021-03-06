# Generated by Django 3.0.10 on 2020-09-24 17:40

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('args', django.contrib.postgres.fields.jsonb.JSONField(default=list, verbose_name='arguments')),
                ('kwargs', django.contrib.postgres.fields.jsonb.JSONField(default=dict, verbose_name='keyword arguments')),
                ('state', models.CharField(choices=[('CANCELED', 'CANCELED'), ('FAILED', 'FAILED'), ('FINISHED', 'FINISHED'), ('PENDING', 'PENDING'), ('STARTED', 'STARTED')], default='PENDING', max_length=50, verbose_name='state')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='finished at')),
                ('metadata', django.contrib.postgres.fields.jsonb.JSONField(default=dict, verbose_name='metadata')),
                ('error', models.TextField(blank=True, null=True, verbose_name='error')),
                ('estimated_duration', models.PositiveIntegerField(blank=True, null=True, verbose_name='estimated duration')),
                ('internal_metadata', django.contrib.postgres.fields.jsonb.JSONField(default=dict, verbose_name='internal metadata')),
            ],
        ),
        migrations.CreateModel(
            name='JobLogEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('logged_at', models.DateTimeField()),
                ('log', django.contrib.postgres.fields.jsonb.JSONField()),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='jobs.Job')),
            ],
            options={
                'verbose_name': 'job log entry',
                'verbose_name_plural': 'job log entries',
            },
        ),
    ]
