from rest_framework import serializers

from .models import Scope


class ScopeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scope
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If skipgeom query param is present, exclude "geom" field
        if 'context' in kwargs:
            if 'request' in kwargs['context']:
                skipgeom = kwargs['context']['request'].query_params.get(
                    'skipgeom', None)
                if skipgeom:
                    self.fields.pop("geom")