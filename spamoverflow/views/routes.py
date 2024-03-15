import json
from flask import Blueprint, jsonify, request
from spamoverflow.models import db 
from spamoverflow.models.email import Email
from datetime import datetime, timedelta
import subprocess
import os
import uuid

# Get the current directory of the Python script
current_directory = os.path.dirname(os.path.abspath(__file__))
# Navigate up two levels to find the folder containing the executable
#parent_directory = os.path.abspath(os.path.join(current_directory, os.pardir))
#randparent_directory = os.path.abspath(os.path.join(parent_directory, os.pardir))
# Name of the executable binary
binary_name = 'spamhammer.exe'
# Construct the path to the binary
binary_path = os.path.join(current_directory, binary_name)
 
api = Blueprint('api', __name__, url_prefix='/api/v1') 
 
@api.route('/health') 
def health():
    """Return a status of 'ok' if the server is running and listening to request"""
    return jsonify({"status": "ok"})

@api.route('/customers/<string:customer_id>/emails', methods=['POST'])
def create_email(customer_id):

    metadata = request.json.get('metadata', {})
    contents = request.json.get('contents', {})
    id = str(uuid.uuid4())
    email_content = f"{contents.get('to')}\n{contents.get('from')}\n{contents.get('subject')}"

    email_json = {
        "id": id,
        "content": email_content,
        "metadata": metadata.get('spamhammer')
    }

    input_file_path = f"{id}input.json"
    output_file_path = f"{id}output.json"

    with open(input_file_path, 'w') as json_file:
        json.dump(email_json, json_file)

    # Run the binary with arguments
    arguments = ["scan", "--input", input_file_path, "--output", output_file_path]
    subprocess.run([binary_path] + arguments)

    email = Email(
        customer_id=customer_id,
        id = id,
        to=contents.get('to'),
        email_from=contents.get('from'),
        subject=contents.get('subject'),
        spamhammer=metadata.get('spamhammer')
    )

    db.session.add(email) 
   
    db.session.commit() 
    return jsonify(email.to_dict()), 201