import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "geolomas.settings")
django.setup()
from measures.models import Device, Measure
from datetime import datetime, timedelta
from random import uniform
import time


def populate(cant_per_day, days, begin_date):
    """
    Populate with randoms measures
        cant_per_day: Quantity of measures in a day - Max 60*24
        days: Quantity of days measured 
        begin_date: datetime to represent the first date measured
    """
    if cant_per_day > 60*24:
        cant_per_day = 60*24
    for d in range(1,days):
        date = begin_date + timedelta(days=d)
        for x in range(1,60*24,int(60*24/cant_per_day)):
            date = date + timedelta(minutes=x)
            for device in Device.objects.all():
                m = Measure.objects.create(
                        datetime=date,  
                        device_id=device.code, 
                        temperature=uniform(20,40),
                        humidity=uniform(70,100)
                )


def periodic_measures(delta):
    """
    Populate database every <delta> seconds 
    """
    while True:
        now = datetime.now()
        for device in Device.objects.all():
            m = Measure.objects.create(
                    datetime=now,  
                    device_id=device.code, 
                    temperature=uniform(20,40),
                    humidity=uniform(70,100)
            )
            print(m)
        time.sleep(delta)



if __name__ == "__main__":
    begin_date = datetime(2019,11,11)
    #populate(16,60,begin_date)
    periodic_measures(3)