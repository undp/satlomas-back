# Configurando un entrenamiento

En este directorio encontramos un ejemplo de como utilizar los archivos de configuración y que significan los campos más importantes en el [archivo template](config_train_lstm_server_template.json).

Un aspecto de la configuración que necesita un poco más de explicación es como se indica al comando de entrenamiento la arquitectura de la red. 

Esta plataforma brinda la posibilidad de elegir, siguiendo ciertas restricciones, la mejor arquitectura a partir de la optimización de una serie de hyper-parametros que caracterizaran distintas opciones de arquitectura. 

En general la red que utilizaremos tendrá un primera capa [`LSTM`](https://www.tensorflow.org/api_docs/python/tf/keras/layers/LSTM) de entrada la cual tendrá `mult * input_variables` neuronas. Luego de esta primera capa tendrémos una capa [`Dropout`](https://www.tensorflow.org/api_docs/python/tf/keras/layers/Dropout) que cumple la función de descartar una porción de las neuronas que le preceden al azar para evitar el over-fitting. El parametro `rate` de esta capa indica cual es la proporción de las neuronas se descarta. 

Luego de la capa inicial, tenemos `mid_layers` capas `LSTM` intermedias que siguen el mismo patrón de configuración:
 * `mult * neuronas_capa_anterior` neuronas 
 * Capa `Dropout` con cierto `rate`
 
Al final tenemos siempre otra capa `LSTM` con el mismo enfoque que las capas anteriores y además una capa [`Dense`](https://www.tensorflow.org/api_docs/python/tf/keras/layers/Dense) con **una** sola neurona de salida

De esta manera, podemos definir una arquitectura mas o menos genérica pero parametrizable. Siempre tendremos una cantidad de neuronas de entrada igual a la cantidad de mediciones pasadas que configuremos en la key `n_past_steps` del archivo y una neurona de salida que será el valor en el futuro a predecir. Sin embargo podremos optimizar (si así lo quisiesemos) la arquitectura intermedia, eligiendo:

1. El valor de `mult` mencionado anteriormente
> Para esto indicamos en el arreglo `hyperopt_pars.mults` los valores que quisieramos evaluar durante la optimización
2. El valor del `rate` para las capas de `Dropout`
> Para esto indicamos en el arreglo `hyperopt_pars.dropout_rate_range` el rango de valores que quisieramos evaluar durante la optimización
3. Cuantas capas intermedias queremos que tenga nuestra red
> Para esto indicamos en el arreglo `hyperopt_pars.mid_layers` los valores que quisieramos evaluar durante la optimización
4. Cuantas veces quisieramos explorar todas las redes posibles a construir usando los rangos hyper-parametros indicados
> Para esto indicamos en `hyperopt_pars.max_evals` cuantas veces quisieramos evaluar todas las combinaciones.


Si ya tenemos decidida cual será la arquitectura a utilizar y queremos ahorrarnos el largo proceso de optimización de la arquitectura para solamente entrenar usando esta arquitectura fija pre-definida, podemos asignar un solo valor a los arreglos del archivo, como en el template que se referencia aquí.