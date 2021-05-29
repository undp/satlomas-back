from auditlog.registry import auditlog
from django.contrib.gis.db import models


class Scope(models.Model):
    CORREDORES = "CE"
    ACR = "AC"
    DISTRITOS = "DI"
    ECOSISTEMAS = "EF"
    ARQUEOLOGICOS = "SA"
    USER_DEFINED = "UD"

    SCOPE_TYPE = [
        (CORREDORES, "Corredores Ecologicos"),
        (ACR, "ACR"),
        (DISTRITOS, "Distritos"),
        (ECOSISTEMAS, "Ecosistemas fragiles"),
        (ARQUEOLOGICOS, "Sitios arqueologicos"),
        (USER_DEFINED, "Definido por usuario"),
    ]

    scope_type = models.CharField(
        max_length=2,
        choices=SCOPE_TYPE,
    )
    geom = models.MultiPolygonField()
    name = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {}".format(self.scope_type, self.name)


auditlog.register(Scope)
