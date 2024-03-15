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

@api.route('/customers/<string:customer_id>/emails/<string:id>', methods=['GET'])
def get_email(customer_id, id):
    email = Email.query.filter_by(customer_id=customer_id, id=id).first()
    return jsonify(email.to_dict()), 201

@api.route('/customers/<string:customer_id>/emails', methods=['GET'])
def get_emails(customer_id):

    # Returns only this many results, 0 < limit <= 1000. Default is 100.
    limit = min(int(request.args.get('limit', 100)), 1000) 
    # Skip this many results before returning, 0 <= offset. Default is 0.
    offset = max(int(request.args.get('offset', 0)), 0) 
    # Only return emails submitted from this date. The date should be in RFC3339 format.
    start= request.args.get('start')
    # Only return emails submitted before this date. The date should be in RFC3339 format.
    end = request.args.get('end') 
    # Only return emails submitted from this email address. The email address should be in the format of user@domain.
    email_from = request.args.get('from') 
    # Only return emails submitted to this email address. The email address should be in the format of user@domain.
    to = request.args.get('to') 
    # Only return emails that have been flagged as malicious.
    only_malicious = request.args.get('only_malicious', type=bool)

    query = Email.query.filter_by(customer_id=customer_id)
    if start:
        query = query.filter(Email.created_at >= start)
    if end:
        query = query.filter(Email.created_at <= end)
    if email_from:
        query = query.filter(Email.email_from == email_from)
    if  to:
        query = query.filter(Email.to == to)
    if only_malicious is not None:
        query = query.filter(Email.malicious == True)

    query = query.limit(limit).offset(offset)
    emails = query.all()
    email_list = []
    
    for email in emails:
        email_list.append(email.to_dict())
    
    return email_list, 201

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

@api.route('/health') 
def health():
    """Return a status of 'ok' if the server is running and listening to request"""
    return jsonify({"status": "ok"})