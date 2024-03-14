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
parent_directory = os.path.abspath(os.path.join(current_directory, os.pardir))
grandparent_directory = os.path.abspath(os.path.join(parent_directory, os.pardir))
# Name of the executable binary
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

    # Run the binary with arguments
    arguments = ["arg1", "arg2", "arg3"]
    subprocess.run([binary_path] + arguments)

    email = Email(
        customer_id = customer_id,
        id = request.json.get('id'),
        to = request.json.get('to'),
        email_from = request.json.get('email_from'),
        subject = request.json.get('subject'),
        body = request.json.get('body')
    )

    db.session.add(email) 
   
    db.session.commit() 
    return jsonify(email.to_dict()), 201