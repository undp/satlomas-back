from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import authentication, permissions
from django.contrib.auth.models import User
from django.shortcuts import render
from vegetation.models import VegetationMask
import shapely.wkt
import pandas as pd
from datetime import datetime
from scopes.models import Scope

# Create your views here.
def intersection_area(geom, date):
    mask = VegetationMask.objects.filter(period=date).first()
    vegetation_geom = shapely.wkt.loads(mask.vegetation.wkt)
    return geom.intersection(vegetation_geom).area


class TimeSeries(APIView):

    def post(self, request):
        data = request.data
        scope_id = data['scope_id'] if 'scope_id' in data else None
        if scope_id is None:
            mp_geometry = data['geometry'] if 'geometry' in data else None
            if mp_geometry is None:
                Exception("No data")
            else:
                geom = shapely.wkt.loads(str(data['geometry']))
        else:
            scope = Scope.objects.get(pk=int(scope_id))
            geom = shapely.wkt.loads(scope.geom.wkt)
        response = {'intersection_area': []}
        fdate = data['from_date'] #must be format %Y-%m-%d 
        edate = data['end_date']
        for date in pd.date_range(fdate,edate,freq='M',).strftime("%Y-%m"): 
            response['intersection_area'].append({
                'date' : datetime.strptime(date, '%Y-%m'),
                'area' : intersection_area(geom, datetime.strptime(date, '%Y-%m'))
            })

        return Response(response)