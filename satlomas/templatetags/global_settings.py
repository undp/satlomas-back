from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def webclient_url():
    return settings.WEBCLIENT_URL
