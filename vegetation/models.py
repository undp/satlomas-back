from django.contrib.gis.db import models

# Create your models here.
class VegetationMask(models.Model):
    period = models.DateField()
    vegetation = models.MultiPolygonField()
    clouds = models.MultiPolygonField()

    class Meta:
        app_label = 'vegetation'

    def save_from_geojson(geojson_path, period):
        from django.contrib.gis.gdal import DataSource
        from django.contrib.gis.geos import GEOSGeometry
        import shapely.wkt
        from shapely.ops import unary_union
        
        ds = DataSource(geojson_path)
        vegetation_polys = []
        clouds_polys = []
        for x in range(0,len(ds[0])-1):
            geom = shapely.wkt.loads(ds[0][x].geom.wkt)
            if str(ds[0][x]['DN']) == '1':
                vegetation_polys.append(geom)
            elif str(ds[0][x]['DN']) == '2':
                clouds_polys.append(geom)
            else:
                pass
        vegetation_mp = unary_union(vegetation_polys)
        clouds_mp = unary_union(clouds_polys)

        return VegetationMask.objects.create(
            period=period,
            vegetation=GEOSGeometry(vegetation_mp.wkt),
            clouds=GEOSGeometry(clouds_mp.wkt)
        )