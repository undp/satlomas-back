import numpy as np
import os
import pandas as pd
import pickle
import sys
import time
import ipdb

from datetime import datetime
from datetime import timedelta
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError

from stations.models import Measurement,Prediction, Place, Station

from geolomasexp.configuration import LSTMHyperoptTrainingScriptConfig
from geolomasexp.data import read_time_series_from_csv

from geolomasexp.feature import (
    get_dataset_from_series,
    get_interest_variable
)

from geolomasexp.model import (
    build_lstm_nnet, 
    eval_regression_performance,
    fit_model, 
    predict_with_model,
    train_val_test_split
)

from geolomasexp.model_hyperopt import (get_lstm_nnet_opt)
from hyperopt import (tpe, hp, fmin)
from keras.models import load_model
from sklearn.metrics import mean_absolute_error, r2_score


# how to run this ? 
# nohup python manage.py predict_lstm config_train_lstm_temp_server_A620_temprature.json 'models/esp:10_eps:200_loss:mean_squared_error_opt:adam_pstps:8_sensor:A620_var:temperature_basenet:4.4_midnet:4.2_hyperoptpars:[2][2][0.1, 0.3]1_model_hyperopt_package_2020-04-22_23:09:03.model' 24 60 >> predict_lstm_temp_A620.log 2>&1 &
class Command(BaseCommand):
   
    """
    Write predictions to database considering the last datetime and the numeric atribute to update
    """
    def save_predictions(self,station_code,predictions,last_datetime,attribute,time_delta):
        station = Station.objects.get(code = station_code)
        pred_datetime = None
        for predicted_value in predictions:
            attributes = dict(temperature=0,
                              humidity=0,
                              wind_speed=0,
                              wind_direction=0,
                              pressure=0,
                              precipitation=0,
                              pm25=0)

            attributes[attribute]= np.float64(predicted_value[0][0])
            
            if not pred_datetime:
                pred_datetime = last_datetime + time_delta
            else: 
                pred_datetime = pred_datetime + time_delta
        
            dt = datetime.utcnow()
            ts = (pred_datetime - np.datetime64('1970-01-01T00:00:00Z')) / np.timedelta64(1, 's')
            dtime = datetime.utcfromtimestamp(ts)
           
            prediction = None
            try:
                prediction = Prediction.objects.get(
                    datetime = dtime,
                    station = station
                    )
            except Exception as e:
                self.log_success('Error trying to get prediction {}'.format(e))

            
            if prediction:
                # update the existing prediction with new prediction value
                prediction.attributes[attribute] = np.float64(predicted_value[0][0])
                prediction.save()
                self.log_success('Prediction updated to {}'.format(prediction))
                
            else:

                prediction , created = Prediction.objects.get_or_create(
                    datetime = dtime,
                    station = station,
                    attributes = attributes
                    )

                self.log_success('New prediction created {}'.format(prediction))


   

    """
    Read a time series from database
    """
    # TODO : we can try using this in the future https://pypi.org/project/django-pandas/
    def read_time_series_from_db(
            self,
            sensor='A601',
            date_col='date',
            hr_col='hr',
            min_col='minute',
            numeric_var='temperature',
            sensor_var='inme',  # TODO : change this for station_code in all the script
            last_n_steps=None  # TODO change this for a number of steps in past
    ):
        # get the station (sensor)
        #station = Station.objects.get(code=sensor)
        # get all the measurements from this station for the last n steps
        measurements = Measurement.objects.filter(station=Station.objects.get(
            code=sensor).id).order_by('-datetime')[:last_n_steps]

        self.log_success(
            'Measures to read from database for sensor {} with query \n{}'.
            format(sensor, measurements.query))

        # get a dataframe from the measurements
        dataset = pd.DataFrame(
            list(measurements.values('datetime', 'attributes')))
        self.log_success('Dataset from database of shape {}'.format(
            dataset.shape))
        # parse datetime column to get sepearae date, hr and minute columns
        dataset[date_col] = dataset.datetime.dt.date
        dataset[hr_col] = dataset.datetime.dt.hour
        dataset[min_col] = dataset.datetime.dt.minute
        # get the numeric var column parsing the json
        dataset[numeric_var] = dataset.attributes.apply(
            lambda x: x[numeric_var])
        dataset[sensor_var] = sensor

        # sort and re-index before returning
        dataset.sort_values([date_col, hr_col,min_col], inplace=True, ascending=True)
        dataset.reset_index(inplace=True)

        self.log_success('Resulting dataset to get datapoints \n:'.format(dataset))

        return dataset

    def log_success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def predict_lstm(self, script_config, model_package_name , future_steps, step_mins = 15):
        """
        Function to use a trained LSTM neural network to predict measurements
        """

        # Read configuration data

        n_past_steps = script_config.n_past_steps

        self.log_success("using {} steps in the past".format(n_past_steps))

        date_col = script_config.date_col
        hr_col = script_config.hr_col
        numeric_var = script_config.numeric_var
        sensor_var = script_config.sensor_var
        target_sensor = script_config.target_sensor
        output_models_path = script_config.output_models_path

        early_stop_patience = script_config.early_stop_patience
        epochs = script_config.epochs

        # Read  dataset slice from n past steps to build the datapoint
        raw_dataset = self.read_time_series_from_db(target_sensor, date_col,
                                                    hr_col, 'minute',
                                                    numeric_var, sensor_var,
                                                    n_past_steps)

        self.log_success("Dataset of shape {} read".format(raw_dataset.shape))

        # TODO : obtener tambien la columna minuto
        # Obtener la variable de interes del dataset
        time_series_dset = get_interest_variable(raw_dataset, sensor_var,
                                                 date_col, hr_col, numeric_var,
                                                 target_sensor)
        self.log_success(
            "Got time series dataset of shape {} with columns {}".format(
                time_series_dset.shape, time_series_dset.columns))
        
        datapoint = time_series_dset[numeric_var].values

        self.log_success("Got datapoint {}".format(datapoint))

        if not model_package_name:
            model_package_name = glob.glob('{}/*_model_hyperopt_package_*.model'.format(output_models_path))[-1]
        
        self.log_success('Using {} packaged model to test'.format(model_package_name))
        
        # IS IT OK to scale here? predict_with_model does not scale so we should here
        with open(model_package_name, 'rb') as file_pi:
            model_package = pickle.load(file_pi)
    
        scaler = model_package['scaler']

        # ensure all data is float
        datapoint = datapoint.astype('float32')
        self.log_success("Got datapoint as float32 {}".format(datapoint))

        datapoint_scaled = scaler.transform(datapoint.reshape(-1, 1))
        self.log_success("Got datapoint_scaled {}".format(datapoint_scaled))
        
        tic = time.time() 
        #pred,mae = predict_with_model(datapoint,model_package_name,future_steps = future_steps)
        pred,mae = predict_with_model(datapoint_scaled,model_package_name,future_steps = future_steps)
        prediction_time = time.time()-tic
        self.log_success('#{},{},prediction_time,{}'.format(model_package_name,future_steps,prediction_time))

        # writing predictions
        time_delta = np.timedelta64(step_mins,'m')
        last_datetime = raw_dataset.tail(1).datetime.values[0] 

        tic = time.time()
        self.save_predictions(target_sensor,pred,last_datetime,numeric_var,time_delta)
        save_time = time.time()-tic
        self.log_success('#{},{},save_time,{}'.format(model_package_name,future_steps,save_time))

    help = '''
    Predict using a LSTM Neural net trained for time series prediction
    
    How to use this?
    
    nohup python manage.py predict_lstm config_train_lstm_temp_server_A620_temprature.json 'models/esp:10_eps:200_loss:mean_squared_error_opt:adam_pstps:8_sensor:A620_var:temperature_basenet:4.4_midnet:4.2_hyperoptpars:[2][2][0.1, 0.3]1_model_hyperopt_package_2020-04-22_23:09:03.model' 24 60 >> predict_lstm_temp_A620.log 2>&1 &
    '''

    #config_file = os.path.join(settings.CONFIG_DIR,'config_train_lstm_temp_server.json')

    def add_arguments(self, parser):
        parser.add_argument(
            'config_file',
            type=str,
            help=
            'File to read configurations from')

        parser.add_argument(
            'model_package_path',
            type=str,
            help=
            'Path of the model pachage file to use to predict')

        parser.add_argument(
            'future_steps',
            type=int,
            help=
            'Steps in the future to predict')
        
        parser.add_argument(
            'step_mins',
            type=int,
            help=
            'How many minutes is a step?')

    def handle(self, *args, **options):

        self.config_file = os.path.join(settings.CONFIG_DIR,options['config_file'])
        self.log_success('Config file read from parameters {}'.format(self.config_file))

        script_config = LSTMHyperoptTrainingScriptConfig(self.config_file)
        self.log_success('Script-config: {}'.format(script_config))


        try:
            model_package_path = options['model_package_path']
            if model_package_path == '':
                model_package_path = None
        except Exception as e :
            self.log_success('Error trying to read model_package_path parameter : {}'.format(e))

        self.log_success('Model package file to call predict_lstm is {}'.format(model_package_path))


        try:
            future_steps = int(options['future_steps'])
        except Exception as e :
            self.log_success('Error trying to read future_steps parameter : {}'.format(e))

        self.log_success('Future steps to call predict_lstm is {}'.format(future_steps))

        try:
            step_mins = int(options['step_mins'])
        except Exception as e :
            self.log_success('Error trying to read step_mins parameter : {}'.format(e))

        self.log_success('Each step is  {} minutes'.format(step_mins))

        self.predict_lstm(script_config,model_package_path,future_steps,step_mins)

