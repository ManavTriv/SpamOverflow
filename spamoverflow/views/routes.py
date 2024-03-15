import json
from flask import Blueprint, jsonify, request
from spamoverflow.models import db 
from spamoverflow.models.email import Email
from datetime import datetime, timedelta
import subprocess
import os
import uuid

# Get the current directory of the Python script and navigate up two levels to find the folder containing the executable
current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.abspath(os.path.join(current_directory, os.pardir))
grandparent_directory = os.path.abspath(os.path.join(parent_directory, os.pardir))
# Executable to run
binary_name = 'spamhammer.exe'
# Construct the path to the binary
binary_path = os.path.join(grandparent_directory, binary_name)
 
api = Blueprint('api', __name__, url_prefix='/api/v1') 
 
@api.route('/health') 
def health():
    """Return a status of 'ok' if the server is running and listening to request"""
    return jsonify({"status": "ok"})

@api.route('/customers/<string:customer_id>/emails', methods=['POST'])
def create_email(customer_id):

    # Extract metadata, and contents from the request
    metadata = request.json.get('metadata', {})
    contents = request.json.get('contents', {})

    # Generate a unique ID for this email
    id = str(uuid.uuid4())

    # Format email contents to be sent to spamhammer
    email_content = f"{contents.get('to')}\n{contents.get('from')}\n{contents.get('subject')}"

    # Input json for spamhammer
    email_json = {
        "id": id,
        "content": email_content,
        "metadata": metadata.get('spamhammer')
    }

    # Denote file paths for the input and output file for spamhammer
    input_file_path = f"{id}_input.json"
    output_file_path = f"{id}_output"

    # Open input JSON file for writing
    with open(input_file_path, 'w') as input_file:
        json.dump(email_json, input_file)

    # Run spamhammer with the required arguments
    arguments = ["scan", "--input", input_file_path, "--output", output_file_path]
    subprocess.run([binary_path] + arguments)

    # Open output JSON file for reading
    with open(f"{output_file_path}.json", 'r') as output_file:
        output_data = json.load(output_file)

    # Create a new email
    email = Email(
        customer_id=customer_id,
        id = id,
        to=contents.get('to'),
        email_from=contents.get('from'),
        subject=contents.get('subject'),
        spamhammer=metadata.get('spamhammer'),
        malicious=output_data.get('malicious')
    )

    # Remove input and output JSON files as they are no longer required
    os.remove(input_file_path)
    os.remove(f"{output_file_path}.json")

    # Add the entry to the database
    db.session.add(email) 
    db.session.commit() 
    return jsonify(email.to_dict()), 201