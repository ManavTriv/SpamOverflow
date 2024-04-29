import json
import os
import subprocess 
 
from celery import Celery
from spamoverflow.models.email import Email 
from spamoverflow.models import db 
from spamoverflow import create_app

app = create_app()

celery = Celery(__name__) 
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL") 
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND") 
celery.conf.task_default_queue = os.environ.get("CELERY_DEFAULT_QUEUE", "scan") 

# Get the directory of the spamhammer and set up spamhammer executable
current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.abspath(os.path.join(current_directory, os.pardir))
binary_name = 'spamhammer.exe'
binary_path = os.path.join(parent_directory, binary_name)

@celery.task(name="scan") 
def create_scan(tasks): 
   
   data = tasks
   email_id = data.get('id')
   email_json = data.get('email_json')
          
   #with app.app_context(): 
   #Find the email    
   email = Email.query.filter_by(id=email_id).first()
    
   # Denote file paths for the input and output file for spamhammer
   input_file_path = f"{email_id}_input.json"
   output_file_path = f"{email_id}_output"
    
   try:
      # Open input JSON file for writing
      with open(input_file_path, 'w') as input_file:
         json.dump(email_json, input_file)
            
      # Run spamhammer with the required arguments
      arguments = ["scan", "--input", input_file_path, "--output", output_file_path]
      subprocess.run([binary_path] + arguments)
        
      # Open output JSON file for reading
      with open(f"{output_file_path}.json", 'r') as output_file:
         output_data = json.load(output_file)
            
      # Update the scanning status
      email.status = "scanned"
      email.malicious = output_data.get('malicious')
      db.session.commit()
        
   except Exception as e:
      # Update teh scanning status
      email.status = "failed"
      db.session.commit()
    
   # Remove input and output JSON files as they are no longer required
   if os.path.exists(input_file_path):
      os.remove(input_file_path)
   if os.path.exists(output_file_path):
      os.remove(output_file_path)
   
   return email_id