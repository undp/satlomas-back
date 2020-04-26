# Generated by Django 3.0.5 on 2020-04-14 15:25

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('scopes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScopeTypeRule',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('scope_type',
                 models.CharField(choices=[('CE', 'Corredores Ecologicos'),
                                           ('AC', 'ACR'), ('DI', 'Distritos'),
                                           ('EF', 'Ecosistemas fragiles'),
                                           ('SA', 'Sitios arqueologicos')],
                                  max_length=2)),
                ('threshold_type',
                 models.CharField(choices=[('A', 'Area'), ('P', 'Percentage')],
                                  max_length=1)),
                ('threshold', models.FloatField(default=5)),
                ('measurement_content_type',
                 models.ForeignKey(limit_choices_to=models.Q(
                     models.Q(('app_label', 'lomas_changes'),
                              ('model', 'coverage_measurements')),
                     models.Q(('app_label', 'vi_lomas_changes'),
                              ('model', 'coverage_measurements')),
                     _connector='OR'),
                                   on_delete=django.db.models.deletion.CASCADE,
                                   to='contenttypes.ContentType')),
                ('user',
                 models.OneToOneField(
                     on_delete=django.db.models.deletion.CASCADE,
                     to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ScopeRule',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('threshold_type',
                 models.CharField(choices=[('A', 'Area'), ('P', 'Percentage')],
                                  max_length=1)),
                ('threshold', models.FloatField(default=5)),
                ('measurement_content_type',
                 models.ForeignKey(limit_choices_to=models.Q(
                     models.Q(('app_label', 'lomas_changes'),
                              ('model', 'coverage_measurements')),
                     models.Q(('app_label', 'vi_lomas_changes'),
                              ('model', 'coverage_measurements')),
                     _connector='OR'),
                                   on_delete=django.db.models.deletion.CASCADE,
                                   to='contenttypes.ContentType')),
                ('scope',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                   to='scopes.Scope')),
                ('user',
                 models.OneToOneField(
                     on_delete=django.db.models.deletion.CASCADE,
                     to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ParameterRule',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('parameter', models.CharField(max_length=64)),
                ('threshold', models.FloatField(default=5)),
                ('user',
                 models.OneToOneField(
                     on_delete=django.db.models.deletion.CASCADE,
                     to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
