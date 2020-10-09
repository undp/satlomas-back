import django.dispatch

# Sent when a new job is started
job_started = django.dispatch.Signal(providing_args=["job"])

# Sent when a job finished, either succesfully or not (failed or canceled)
job_finished = django.dispatch.Signal(providing_args=["job"])

# Sent when a job finishes with a FAILED status
job_failed = django.dispatch.Signal(providing_args=["job"])

# Sent when a job finishes with a CANCELED status (i.e. canceled by the user)
job_canceled = django.dispatch.Signal(providing_args=["job"])