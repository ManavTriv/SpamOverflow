import json
from flask import Blueprint, jsonify, request
from spamoverflow.models import db 
from spamoverflow.models.email import Email
from datetime import datetime
from urllib.parse import urlparse
import subprocess
import os
import uuid
import re

# Get the current directory of the Python script and navigate up two levels to find the folder containing the executable
current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.abspath(os.path.join(current_directory, os.pardir))
#grandparent_directory = os.path.abspath(os.path.join(parent_directory, os.pardir))
# Executable to run
binary_name = 'spamhammer.exe'
# Construct the path to the binary
binary_path = os.path.join(parent_directory, binary_name)
 
api = Blueprint('api', __name__, url_prefix='/api/v1') 

@api.route('/customers/<string:customer_id>/emails/<string:id>', methods=['GET'])
def get_email(customer_id, id):
    try:
        if not customer_id or not id:
            return jsonify({'error': 'Body/Path parameter was malformed or invalid.'}), 400
        email = Email.query.filter_by(customer_id=customer_id, id=id).first()
        if email is None: 
            return jsonify({'error': 'The requested email for the customer does not exist.'}), 404 
        return jsonify(email.to_dict()), 200
    except Exception as e:
         return jsonify({'error': 'An unknown error occurred trying to procress the request: {}'.format(str(e))}), 500

@api.route('/customers/<string:customer_id>/emails', methods=['GET'])
def get_emails(customer_id):
    try:
        # Returns only this many results, 0 < limit <= 1000. Default is 100.
        limit = min(int(request.args.get('limit', 100)), 1000) 
        # Skip this many results before returning, 0 <= offset. Default is 0.
        offset = max(int(request.args.get('offset', 0)), 0) 
        # Only return emails submitted from this date. The date should be in RFC3339 format.
        start = request.args.get('start')
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
        
        return email_list, 200
    except Exception as e:
         return jsonify({'error': 'An unknown error occurred trying to procress the request: {}'.format(str(e))}), 500

@api.route('/customers/<string:customer_id>/emails', methods=['POST'])
def create_email(customer_id):
    try:
        # Extract metadata, and contents from the request
        metadata = request.json.get('metadata', {})
        contents = request.json.get('contents', {})

        # Generate a unique ID for this email
        id = str(uuid.uuid4())

        # Format email contents to be sent to spamhammer
        email_content = f"{contents.get('to')}\n{contents.get('from')}\n{contents.get('subject')}\n{contents.get('body')}"
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

        # URL pattern to search for
        url_pattern = r'\bhttps?://\S+\b'
        # Find all URLS in subject of email
        urls = re.findall(url_pattern, contents.get('body'),)
        # Extract domains from URLs
        domains_array = set()
        for url in urls:
            parsed_url = urlparse(url)
            domains_array.add(parsed_url.netloc)
        # Store emails in a single array
        domains = ';'.join(domains_array)

        # Create a new email
        email = Email(
            customer_id=customer_id,
            id = id,
            to = contents.get('to'),
            email_from = contents.get('from'),
            subject = contents.get('subject'),
            spamhammer = metadata.get('spamhammer'),
            status = "scanned",
            malicious = output_data.get('malicious'),
            domains = domains
        )

        # Remove input and output JSON files as they are no longer required
        os.remove(input_file_path)
        os.remove(f"{output_file_path}.json")
        # Add the entry to the database
        db.session.add(email) 
        db.session.commit() 
        return jsonify(email.to_dict()), 201
    
    except Exception as e:
         return jsonify({'error': 'An unknown error occurred trying to procress the request: {}'.format(str(e))}), 500

@api.route('/customers/<string:customer_id>/reports/actors', methods=['GET'])
def get_actors(customer_id):
    try:
        #actors = db.session.query(Email.email_from, func.count(Email.email_from).label('count')).group_by(Email.sender).all()
        actors = Email.query.filter_by(customer_id=customer_id, malicious=True).group_by(Email.email_from).all()
        
        actors_data = []
        for actor in actors:
            actor_data = {
                'id': actor.email_from,
                'count': Email.query.filter_by(customer_id=customer_id, email_from=actor.email_from, malicious=True).count()
            }
            actors_data.append(actor_data)

        report = {
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'total': len(actors_data),
            'data': actors_data
        }

        return jsonify(report), 200
    except Exception as e:
         return jsonify({'error': 'An unknown error occurred trying to procress the request: {}'.format(str(e))}), 500

@api.route('/customers/<string:customer_id>/reports/domains', methods=['GET'])
def get_domains(customer_id):
    try:
        domains = Email.query.filter_by(customer_id=customer_id, malicious=True).group_by(Email.domains).all()

        domains_data = []
        for domain in domains:
            domain_data = {
                'id': domain.domains,
                'count': Email.query.filter_by(customer_id=customer_id, domains=domain.domains, malicious=True).count()
            }
            domains_data.append(domain_data)

        response = {
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'total': len(domains_data),
            'data': domains_data
        }

        return jsonify(response), 200
    except Exception as e:
         return jsonify({'error': 'An unknown error occurred trying to procress the request: {}'.format(str(e))}), 500


@api.route('/customers/<string:customer_id>/reports/recipients', methods=['GET'])
def get_recipients(customer_id):
    try:
        recipients = Email.query.filter_by(customer_id=customer_id, malicious=True).group_by(Email.email_from).all()
        
        recipients_data = []
        for recipient in recipients:
            recipient_data = {
                'id': recipient.to,
                'count': Email.query.filter_by(customer_id=customer_id, to=recipient.to, malicious=True).count()
            }
            recipients_data.append(recipient_data)

        report = {
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'total': len(recipients_data),
            'data': recipients_data
        }

        return jsonify(report), 200
    except Exception as e:
         return jsonify({'error': 'An unknown error occurred trying to procress the request: {}'.format(str(e))}), 500

@api.route('/health') 
def health():
    try:
        return jsonify({'status': 'Service is healthy'}), 200
    except Exception as e:
        return jsonify({'error': 'Service is not healthy: {}'.format(str(e))}), 500