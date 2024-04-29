import os 
 
from celery import Celery 
 
celery = Celery(__name__) 
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL") 
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND") 
celery.conf.task_default_queue = os.environ.get("CELERY_DEFAULT_QUEUE", "ical") 
 
@celery.task(name="ical") 
def create_ical(tasks): 
   return "Hello World"