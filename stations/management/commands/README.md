# Comandos disponibles
Encontramos en este directorio algunos comandos Django accesorios al funcionamiento de la plataforma.

## Entrenamiento de redes neuronales LSTM para predicción de variables meteorológicas

Es posible usar el comando [`train_lstm_hyperopt`](train_lstm_hyperopt.py) ubicado en este directorio para entrenar una red neuronal del tipo [LSTM](https://en.wikipedia.org/wiki/Long_short-term_memory) que pueda ser usada para predecir valores futuros de las variables meteorológicas que se registran en esta plataforma.

Este comando lee registros de la tabla `Measurement`  de la base de datos y las usa para el entrenamiento. Por el momento el comando solo puede entrenar un modelo para una combinación de `Station` y variable meteorológica (temperatura, humedad, etc).

Para ejecutar este comando se debe:
1. Ubicar en la carpeta raíz del proyecto  `satlomas-back`
2. Ejecutar el comando

```
python manage.py train_lstm_hyperopt <archivo_de_configuracion> <fecha_desde> <which_minute>
```


El parámetro `<archivo_de_configuracion>` es un archivo `.json` que debe estar ubicado en `satlomas-back/config/`. Este archivo debe contener la información de configuración del entrenamiento que además luego será usada para realizar predicciones. Debemos tener tantos archivos de configuración como modelos (estación,variable) quisieramos entrenar y usar para predecir. Para entender mejor como configurar un entranemiento mediante este archivo puede ver el [README correspondiente](../../../config/README.md).

El parámetro `<fecha_desde>` impone un limite de tiempo para leer los datos usados para entrenar. Está fecha debe tener el formato `YYYY-MM-DD`.

Finalmente el parámetro `<which_minute>` nos permite indicar cual minuto de la hora usaremos para sub-muestrear los datapoints. Por ejemplo si indicamos `15`, decimos que solo usamos medidas de las horas y cuarto.

Cuando el comando finalice su ejecución deberiamos tener en la carpeta `satlomas-back/models/` varios archivos y entre ellos uno con el siguiente formato :

> `models/*_model_hyperopt_package_*.model`

Este archivo representa esta instancia de entrenamiento y contiene el modelo y otra información necesaria para hacer predicciones. Cabe recordar que este archivo corresponde al modelo para **una estacion** y **un atributo** en particular.

Además tendremos en la carpeta `satlomas-back/results/` un archivo `.csv` donde reportamos las medidas obtenidas.

Un ejemplo concerto de como ejecutar este comando para usar mediciones desde Enero de 2011 y tomando solo mediciones de cada hora, sería:

```
nohup python manage.py train_lstm_hyperopt config_train_lstm_server_template.json 2011-01-01 0 >> archivo_para_logear.log 2>&1 &
```



## Predicción de variables meteorológicas usando redes neuronales LSTM

Es posible usar el comando [`predict_lstm`](predict_lstm.py) ubicado en este directorio para aplicar una red neuronal del tipo [LSTM](https://en.wikipedia.org/wiki/Long_short-term_memory) pre-entrenada y predecir valores futuros de las variables meteorológicas que se registran en esta plataforma.

Este comando lee las ultimas mediciones registradas en la base de datos y luego de proecesarlas para un formato adecuado, las provee al modelo para predecir valores futuros de la variable de interes.

Para ejecutar el comando se debe:

 1. Ubicarse en la carpeta raíz del proyecto satlomas-back
 2. Ejecutar el comando

```
python manage.py predict_lstm <archivo_de_configuracion> <model_package_path> <future_steps> <step_mins>
```

El primer parametro de este comando es el MISMO `<archivo_de_configuracion>` usado para entrenar el modelo que usaremos, el cual describimos anteriormente y explicamos en detalle [aquí](../../../config/README.md).

El parámetro `<model_package_path>` es una cadena que indica la ruta al modelo que quisieramos usar para predecir y fue generado con el archivo de configuración pasado como primer parametro.

Luego indicamos con el número entero `<future_steps>`  cuantos pasos hacia adelante queremos realizar predicciones.

El último parametro `<step_mins>` indica cuantos mínutos hay en un time-step. Por ejemplo, si `future_steps=24` y `step_mins=60`, vamos a predecir `24` periodos adelante y cada periodo será de `60` minutos por lo que iremos un día adelante. El valor de `<step_mins>` debe corresponderse con el sampleo usado para entrenar, por lo que si para entrenar el periodo de tiempo considerado para cada time-step fue de una hora, aqui ponemos `60`. Si hubiesemos usado muestras cada `15` minutos aqui iria el numero `15`.

Como resultado de ejecutar este comando deberiamos tener en la base de datos tantos registros en la tabla de `Prediction` como pasos generemos. Cada registro tiene el mismo formato que las `Measurement` solo que referencia predicciones, es decir valores obtenidos con el modelo, y no reales. Además este comando al ser ejecutado, si encuentra una prediccion anterior para el mismo momento en el tiempo, la actualiza con la nueva prediccion.

Un ejemplo de como correr este comando para predecir `temperaturas` de la estaciíón 'A620' hasta 24 horas al futuro, sería

```
nohup python manage.py predict_lstm config_train_lstm_server_template.json 'models/esp:10_eps:200_loss:mean_squared_error_opt:adam_pstps:8_sensor:A620_var:temperature_basenet:4.4_midnet:4.2_hyperoptpars:[2][2][0.1, 0.3]1_model_hyperopt_package_2020-04-22_23:09:03.model' 24 60 >> log_predicciones.log 2>&1 &
```
