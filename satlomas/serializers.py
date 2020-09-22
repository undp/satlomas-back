from datetime import date

import rest_auth
from django.conf import settings


class PasswordResetSerializer(rest_auth.serializers.PasswordResetSerializer):
    def get_email_options(self):
        return {
            'email_template_name': 'registration/password_reset_message.txt',
            'html_email_template_name':
            'registration/password_reset_message.html',
            'extra_email_context': self.extra_email_context,
        }

    @property
    def extra_email_context(self):
        return {
            'preview_text': '',
            'current_year': date.today().year,
            'company_name': settings.COMPANY_NAME,
            'mailing_address': settings.LIST_ADDRESS_HTML,
            'contact_email': settings.CONTACT_EMAIL,
        }
