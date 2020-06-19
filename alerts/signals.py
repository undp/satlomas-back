from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail

from .models import UserProfile , Alert


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=Alert)
def send_email(sender, instance, created, **kwargs):
    print('send_email')
    profile = UserProfile.objects.get(user=instance.user)
    if profile.email_alerts == True:
        print('llama a send_mail')
        send_mail('GeoLomas Notificaciones', 
            'Notificación de prueba', 
            'notifications@dymaxionlabs.com', 
            [instance.user.email]
        )
