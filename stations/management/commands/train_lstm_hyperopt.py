import os
import pickle
import sys
import time
from datetime import datetime

import pandas as pd
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError

from geolomasexp.configuration import LSTMHyperoptTrainingScriptConfig
from geolomasexp.data import read_time_series_from_csv
from geolomasexp.feature import get_dataset_from_series, get_interest_variable
from geolomasexp.model import (build_lstm_nnet, eval_regression_performance,
                               fit_model, train_val_test_split)
from geolomasexp.model_hyperopt import get_lstm_nnet_opt
from hyperopt import fmin, hp, tpe
from keras.models import load_model
from sklearn.metrics import mean_absolute_error, r2_score , max_error
from stations.models import Measurement, Place, Station

'''
This command is used to train a LSTM Neural Network to use a predefined number of past values of a variable
of interest to predict future values of the same variable.

You should run this command for each combination of Station and interest variable that you need a model for

run this by: 
nohup python manage.py train_lstm_hyperopt config_train_lstm_temp_server_A620_temprature.json 2011-01-01 0 >> train_lstm_temp_A620.log 2>&1 &
''' 
class Command(BaseCommand):

    '''
        Read a time series from database and return it as a DataFrame
    '''
    def read_time_series_from_db(
            self,
            sensor='A601',
            date_col='date',
            hr_col='hr',
            min_col='minute',
            numeric_var='temperature',
            sensor_var='inme',  # TODO : change this for station_code in all the script
            date_since=None,
            which_minutes = [0,15,30,45]
            ):      
        # get all the measurements from this station
        measurements = Measurement.objects.filter(station=Station.objects.get(
            code=sensor).id)
        if date_since is not None:
            # we only get since date_since if we have this filter
            measurements = measurements.filter(datetime__gte=date_since)
        self.log_success(
            'Measurements to read from database for sensor {} with query \n{}'.
            format(sensor, measurements.query))
        # get a dataframe from the measurements
        dataset = pd.DataFrame(
            list(measurements.values('datetime', 'attributes')))
        self.log_success('Dataset from database of shape {}'.format(
            dataset.shape))
        # parse datetime column to get sepearate date, hr and minute columns
        dataset[date_col] = dataset.datetime.dt.date
        dataset[hr_col] = dataset.datetime.dt.hour
        dataset[min_col] = dataset.datetime.dt.minute
        # get the interest variable column parsing the json
        dataset[numeric_var] = dataset.attributes.apply(
            lambda x: x[numeric_var])
        dataset[sensor_var] = sensor
        # sort and re-index before returning
        dataset.sort_values([date_col, hr_col], inplace=True, ascending=True)
        dataset.reset_index(inplace=True)
        # only return the datapoints of the corresponding minutes we asked
        return dataset.loc[dataset.minute.isin(which_minutes)]

    '''
        Util function to log
    '''
    def log_success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    '''
        Function to train an LSTM neural network looking at the past
    '''
    def train_lstm(self, script_config, since_date,which_minutes):

        time_stmp = datetime.now()
        # get a string with the timestamp to configure this training and save everything with this stamp
        time_stmp_str = time_stmp.strftime("%Y-%m-%d_%H:%M:%S")
        # we will look this number of steps in the past, reading from configuration
        n_past_steps = script_config.n_past_steps

        self.log_success("using {} steps in the past".format(n_past_steps))
        # extracting more configuration variables
        date_col = script_config.date_col
        hr_col = script_config.hr_col
        numeric_var = script_config.numeric_var
        sensor_var = script_config.sensor_var
        target_sensor = script_config.target_sensor
        output_models_path = script_config.output_models_path
        output_results_path = script_config.output_results_path
        # these are the hyper parameters related to the arquitecture of the Net to optimize over
        hyperopt_pars = script_config.hyperopt_pars
        # configuration values related to the optimizer
        model_loss = script_config.model_loss
        optimizer = script_config.optimizer
        # configuration values related to the training process
        early_stop_patience = script_config.early_stop_patience
        epochs = script_config.epochs

        date_since = datetime(int(since_date[0]), int(since_date[1]),
                              int(since_date[2]))
        # read the data from the database as time series
        raw_dataset = self.read_time_series_from_db(target_sensor, date_col,
                                                    hr_col, 'minute',
                                                    numeric_var, sensor_var,
                                                    date_since,
                                                    which_minutes
                                                   )
        self.log_success("Dataset of shape {} read".format(raw_dataset.shape))

        # we get the variable we want to train model on from the dataset
        time_series_dset = get_interest_variable(raw_dataset, sensor_var,
                                                 date_col, hr_col, numeric_var,
                                                 target_sensor)
        self.log_success(
            "Got time series dataset of shape {} with columns {}".format(
                time_series_dset.shape, time_series_dset.columns))
        # with this we turn the tabular data in time series examples
        sup_dataset, scaler = get_dataset_from_series(time_series_dset,
                                                      n_past_steps)
        self.log_success(
            "Got supervised dataset of shape {} with columns {}".format(
                sup_dataset.shape, sup_dataset.columns))

        # saving the scaler for future predictions if needed
        with open(
                '{}{}_hyperopt_scaler_{}.pickle'.format(
                    output_models_path, str(script_config), time_stmp_str),
                'wb') as file_pi:
            pickle.dump(scaler, file_pi)

        # the number of features is the number of past setps of the dataset 
        n_features = time_series_dset.shape[1]
        # spliting into train, validation and test sets
        dataset_splits = train_val_test_split(sup_dataset, n_past_steps,
                                              n_features, numeric_var)
        self.log_success("Got split:")
        for key in dataset_splits.keys():
            self.log_success("{} shapes: {},{}".format(
                key, dataset_splits[key]['X'].shape,
                dataset_splits[key]['y'].shape))
        # get the trainset from the split
        trainset = dataset_splits['trainset']
        # generating the file names for the model, history and so on
        out_model_name = '{}{}_hyperopt_model_{}.hdf5'.format(
            output_models_path, str(script_config), time_stmp_str)

        history_out_name = '{}{}_hyperopt_history_{}.pickle'.format(
            output_models_path, str(script_config), time_stmp_str)
        # getting the array of multipliers to optimize on from the configuration
        mults = hyperopt_pars['mults']
        # also the dropout range
        dropout_rate_range = hyperopt_pars['dropout_rate_range']
        # and the number of mid layers
        n_mid_layers = hyperopt_pars['mid_layers']

        self.log_success(
            "LSTM NNNet hyperpars to optimize on: mults:{}, dropout:{}, n mid layers:{}"
            .format(mults, dropout_rate_range, n_mid_layers))

        tic = time.time()
        # this builds the space of possible configurations to optimize over by training and evalauting multiple Nets
        space = hp.choice('nnet_config', [{
            'dataset_splits':
            dataset_splits,
            'mult_1':
            hp.choice('mult_1', mults),
            'dropout_rate_1':
            hp.uniform('dropout_rate_1', dropout_rate_range[0],
                       dropout_rate_range[1]),
            'mult_mid':
            hp.choice('mult_mid', mults),
            'dropout_rate_mid':
            hp.uniform('dropout_rate_mid', dropout_rate_range[0],
                       dropout_rate_range[1]),
            'mult_n':
            hp.choice('mult_n', mults),
            'dropout_rate_n':
            hp.uniform('dropout_rate_n', dropout_rate_range[0],
                       dropout_rate_range[1]),
            'n_mid_layers':
            hp.choice('n_mid_layers', n_mid_layers),
            'model_loss':
            model_loss,
            'optimizer':
            optimizer,
            'target_var':
            numeric_var,
            'output_models_path':
            output_models_path,
            'early_stop_patience':
            early_stop_patience,
            'epochs':
            epochs,
            'time_stmp_str':
            time_stmp_str,
            'out_model_name':
            out_model_name,
            'history_out_name':
            history_out_name
        }])
        # this is the actual call to the search process for minimization of loss
        optimal_pars = fmin(get_lstm_nnet_opt,
                            space,
                            algo=tpe.suggest,
                            max_evals=hyperopt_pars['max_evals'])

        opt_time = time.time() - tic
        self.log_success(
            "Hyper parameter optimization for optimal pars {} took {} seconds for {} datapoints"
            .format(optimal_pars, opt_time, trainset['X'].shape[0]))

        # saving the optimal architecture
        with open(
                '{}{}_hyperopt_optimal_pars_{}.pickle'.format(
                    output_models_path, str(script_config), time_stmp_str),
                'wb') as file_pi:
            pickle.dump(optimal_pars, file_pi)

        # building the final Net with the best choice made by the optimization process
        # first and last layer configuration
        base_config_opt = {
            "first_layer": {
                "mult": int(mults[optimal_pars['mult_1']]),
                "dropout_rate": float(optimal_pars['dropout_rate_1'])
            },
            "last_layer": {
                "mult": int(mults[optimal_pars['mult_n']]),
                "dropout_rate": float(optimal_pars['dropout_rate_n'])
            }
        }
        # mid layers configuration
        mid_layers_config_opt = {
            "n_layers": int(n_mid_layers[optimal_pars['n_mid_layers']]),
            "mult": int(mults[optimal_pars['mult_mid']]),
            "dropout_rate": float(optimal_pars['dropout_rate_mid'])
        }
        # actually building the Net with the best architecture
        lstm_nnet_arq = build_lstm_nnet(trainset['X'], base_config_opt,
                                        mid_layers_config_opt, model_loss,
                                        optimizer)
        self.log_success(
            "Build LSTM NNet with optimal parameters \n {}".format(
                lstm_nnet_arq.summary()))

        # now we train again with the best Net over the full trainset
        tic = time.time()
        lstm_nnet = fit_model(lstm_nnet_arq, trainset,
                              dataset_splits['valset'], target_sensor,
                              numeric_var, output_models_path,
                              early_stop_patience, epochs, time_stmp_str,
                              out_model_name, history_out_name)
        train_time = time.time() - tic
        self.log_success(
            "Trained LSTM NNet {} took {} seconds for {} datapoints".format(
                lstm_nnet, train_time, trainset['X'].shape[0]))

        tic = time.time()
        # we evalaute MAE the trained net over trainset
        train_mae = eval_regression_performance(trainset,
                                                lstm_nnet,
                                                scaler,
                                                measure=mean_absolute_error)
        train_eval_time = time.time() - tic
        self.log_success("Train MAE {} and took {} seconds".format(
            train_mae, train_eval_time))

        tic = time.time()
        # we evalaute MAE the trained net over testset
        test_mae = eval_regression_performance(dataset_splits['testset'],
                                               lstm_nnet,
                                               scaler,
                                               measure=mean_absolute_error)
        test_eval_time = time.time() - tic
        self.log_success("Test MAE {} and took {} seconds".format(
            test_mae, test_eval_time))
        # evaluate R2 as well over train
        train_r2 = eval_regression_performance(trainset,
                                               lstm_nnet,
                                               scaler,
                                               measure=r2_score)
        self.log_success("Train R2 {}".format(train_r2))
        # and test
        test_r2 = eval_regression_performance(dataset_splits['testset'],
                                              lstm_nnet,
                                              scaler,
                                              measure=r2_score)
        self.log_success("Test R2 {}".format(test_r2))
        
        # also Maximum Error
        train_max_e = eval_regression_performance(trainset,
                                                lstm_nnet,
                                                scaler,
                                                measure=max_error)

        self.log_success("Train MAXE {} ".format(train_max_e))

        test_max_e = eval_regression_performance(dataset_splits['testset'],
                                               lstm_nnet,
                                               scaler,
                                               measure=max_error)

        self.log_success("Test MAXE {}".format(test_max_e))


        # Saving the training results to a csv table
        results = pd.DataFrame({
            'sensor': [target_sensor],
            'target_variable': [numeric_var],
            'hyperopt_pars': [hyperopt_pars],
            'optimal_pars': [optimal_pars],
            'model_loss': [model_loss],
            'optimizer': [optimizer],
            'early_stop_patience': [early_stop_patience],
            'epochs': [epochs],
            'train_mae': [train_mae],
            'test_mae': [test_mae],
            'train_r2': [train_r2],
            'test_r2': [test_r2],
            'train_max_e': [train_max_e],
            'test_max_e': [test_max_e],
            'train_time': [train_time],
            'train_eval_time': [train_eval_time],
            'test_eval_time': [test_eval_time],
            'trainset_size': [trainset['X'].shape[0]]
        })
        results.to_csv('{}{}_hyperopt_results_{}.csv'.format(
            output_results_path, str(script_config), time_stmp_str),
                       index=False)

        # Also we pack the model, scaler, optimal parameters and test MAE for future use in predictions
        model_package = {
            'model': lstm_nnet,
            'scaler': scaler,
            'test_mae': test_mae,
            'optimal_pars': optimal_pars
        }

        with open(
                '{}{}_model_hyperopt_package_{}.model'.format(
                    output_models_path, str(script_config), time_stmp_str),
                'wb') as file_pi:
            pickle.dump(model_package, file_pi)

    help = 'Train (and optimize) a LSTM Neural net for time series prediction'

    config_file = os.path.join(settings.CONFIG_DIR,
                               'config_train_lstm_temp_server.json')

    def add_arguments(self, parser):
        parser.add_argument(
            'config_file',
            type=str,
            help=
            'File to read configurations from')
        
        parser.add_argument(
            'since_date',
            type=str,
            help=
            'YYYY-MM-DD date since when we are fetching measurements to train')
        
        parser.add_argument(
            'which_minute',
            type=int,
            help=
            'Which minute of the hour to consider, pass 0 or negative to get all the hour')

    def handle(self, *args, **options):
        # parameter parsing
        self.config_file = os.path.join(settings.CONFIG_DIR,options['config_file'])
        self.log_success('Config file read from parameters {}'.format(self.config_file))

        since_date = options['since_date'].split('-')
        self.log_success('Since date argument {}'.format(since_date))
        
        which_minute = int(options['which_minute'])
        self.log_success('which_minute argument {}'.format(which_minute))
        
        if which_minute <= 0 :
            # if we pass negative values, we choose to use the whole hour
            which_minutes = range(60)
        else:
            which_minutes = [which_minute]
        # instantiate the configuration
        script_config = LSTMHyperoptTrainingScriptConfig(self.config_file)
        self.log_success('Script-config: {}'.format(script_config))
        # call the training process 
        self.train_lstm(script_config, since_date,which_minutes)
