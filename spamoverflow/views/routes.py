from flask import Blueprint, jsonify, request
from spamoverflow.models import db 
from spamoverflow.models.email import Email
from datetime import datetime, timedelta
import subprocess
import uuid

binary_path = 'C:\Users\trive\Desktop\6400'
 
api = Blueprint('api', __name__, url_prefix='/api/v1') 
 
@api.route('/health') 
def health():
    """Return a status of 'ok' if the server is running and listening to request"""
    return jsonify({"status": "ok"})

@api.route('/customers/<string:customer_id>/emails', methods=['POST'])
def create_email(customer_id):

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