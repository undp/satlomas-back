from django.utils.translation import ugettext_lazy as _
from rest_framework import authentication, exceptions
from rest_framework.authentication import get_authorization_header


class TokenAuthentication(authentication.TokenAuthentication):
    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or (len(auth) > 1
                        and auth[0].lower() != self.keyword.lower().encode()):
            return None

        if len(auth) > 2:
            msg = _(
                'Invalid token header. Token string should not contain spaces.'
            )
            raise exceptions.AuthenticationFailed(msg)

        try:
            if len(auth) == 2:
                token = auth[1].decode()
            else:
                token = auth[0].decode()
        except UnicodeError:
            msg = _(
                'Invalid token header. Token string should not contain invalid characters.'
            )
            raise exceptions.AuthenticationFailed(msg)

        return self.authenticate_credentials(token)
