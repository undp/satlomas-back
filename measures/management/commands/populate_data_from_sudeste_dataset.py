import json
import os
import pandas as pd

from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from measures.models import Measure, Place, Station
from django.contrib.gis.geos import Point



# run this by python manage.py populate_data_from_sudeste_dataset >> populate_data.log 2>&1 &
class Command(BaseCommand):
    
    def log_success(self,msg):
        self.stdout.write(self.style.SUCCESS(msg))
        
    def process_measure_row(self,station,measure):
        
        direction = 1
        
        for minute in [0,15,30,45]:

            try :
                the_year = measure.yr
            except:
                pass
            
            try :
                the_mo = measure.mo
            except:
                pass
            
            try:
                the_day = measure.da
            except:
                pass
            
            try:
                the_hr = measure.hr
            except:
                pass
            
            
            timestamp = datetime(the_year, the_mo, the_day, the_hr, minute, 0, 0)
            self.log_success('Timetamp to save {}'.format(timestamp))
            
            delta_min = direction * 0.02 * minute
            direction = direction * -1
            
            attributes = dict(
                temperature=measure.temp + delta_min,
                humidity_rel=measure.hmdy + delta_min,
                wind_speed=measure.wdsp + delta_min,
                wind_direction=measure.wdct + delta_min,
                pressure=measure.stp + delta_min,
                precipitation=measure.prcp + delta_min,
                particulate_matter=measure.prcp*2 + delta_min
            )
            self.log_success('Attributes to save {}'.format(attributes))

            try:
                new_measure, created = Measure.objects.get_or_create(
                    datetime = timestamp,
                    station = station,
                    attributes = attributes
                )

                if created :
                    self.log_success('Measure created: {}'.format(new_measure))
                else:
                    self.log_success('Measure already exists'.format(new_measure))
            except Exception as e:
                self.log_success('Exception trying to create measure'.format(e))
                

        
    help = 'Import place, station and measurement data from sudeste dataset'

    CSV_PATH = os.path.join(settings.DATA_DIR,'sudeste_sample.csv')

    def handle(self, *args, **options):

        dataset = pd.read_csv(self.CSV_PATH, header=0, index_col=0,nrows=None)
        self.log_success('Shape of the original csv {}'.format(dataset.shape))
        
        #drop data to make it managable
        dataset = dataset.loc[dataset.yr > 2010]
        
        dataset.fillna(0,inplace=True)
        
        self.log_success('Shape of the filtered csv {}'.format(dataset.shape))
        
        # get all the different cities in the dataset
        unique_cities = dataset.city.unique()

        for city in unique_cities:
            self.log_success('Creating place for city {}'.format(city))
            place, created = Place.objects.get_or_create(name = city)
            if created :
                self.log_success('Place for {} created'.format(city))
            else:
                self.log_success('Place for {} already exists'.format(city))    
            
            # create the stations of the city
            # work with a the slice of the dataset for that city dataset.loc[dataset.city == city]
            
            unique_stations = dataset.loc[dataset.city == city].inme.unique()
            for station_code in unique_stations:
                
                # work with slice for city and station
                #dataset.loc[dataset.city == city].loc[dataset.loc[dataset.city == city].inme == station_code]
                
                first = dataset.loc[dataset.city == city].loc[dataset.loc[dataset.city == city].inme == station_code].iloc[0]
                
                self.log_success('Creating station {}'.format(station_code))
                station, created = Station.objects.get_or_create(
                    code = station_code,
                    name = first.wsnm,
                    lat = float(first.lat),lon=float(first.lon),
                    place=place
                )
                if created :
                    self.log_success('Station {} created: {}'.format(station_code,station))
                else:
                    self.log_success('Station {} already exists'.format(station))    
                    
                #get all measures for station , probably simulating or imputing values between hours
                # dataset.loc[dataset.inme == station_code]
                
                dataset.loc[dataset.inme == station_code].apply(lambda x : self.process_measure_row(station,x),axis=1)
                
                


                

         
            
                
