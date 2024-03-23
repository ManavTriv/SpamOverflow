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

# Get the directory of the spamhammer and set up spamhammer executable
current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.abspath(os.path.join(current_directory, os.pardir))
binary_name = 'spamhammer.exe'
binary_path = os.path.join(parent_directory, binary_name)
 
api = Blueprint('api', __name__, url_prefix='/api/v1') 

# Function to check if input is a valud UUID
def is_uuid(input):
    try:
        uuid.UUID(input)
        return True
    except:
        return False

@api.route('/customers/<string:customer_id>/emails', methods=['GET'])
def get_emails(customer_id):
    try:

        if not is_uuid(customer_id):
            return jsonify({'error': 'Customer ID is not a valid UUID'}), 400

        try:
            limit = int(request.args.get("limit", 100))
            offset = int(request.args.get("offset", 0))
        except:
            return jsonify({'error': 'Invalid query parameters'}), 400
    
        start = request.args.get('start')
        end = request.args.get('end') 
        email_from = request.args.get('from') 
        to = request.args.get('to') 
        state = request.args.get('state')
        only_malicious = request.args.get('only_malicious')
        
        if limit <= 0 or limit > 1000 or offset < 0:
            return jsonify({'error': 'Invalid query parameters'}), 400 
        
        rfc3339_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$'
        
        if (start and not re.match(rfc3339_pattern, start)) or (end and not re.match(rfc3339_pattern, end)):
            return jsonify({'error': 'Invalid query parameters'}), 400 
        
        email_pattern = r'^\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b$'
        
        if (email_from and not re.match(email_pattern, email_from)) or (to and not re.match(email_pattern, to)):
            return jsonify({'error': 'Invalid query parameters'}), 400 
        
        states = ['pending', 'scanned', 'failed']
        
        if (state and state not in states):
            return jsonify({'error': 'Invalid query parameters'}), 400 
    
        if only_malicious:
            if only_malicious.lower() == 'true':
                only_malicious = True
            elif only_malicious.lower() == 'false':
                only_malicious = False
            else:
                return jsonify({'error': 'Invalid query parameters'}), 400 
            
        query = Email.query.filter_by(customer_id=customer_id)

        if start:
            start_datetime = datetime.fromisoformat(start)
            query = query.filter(Email.created_at >= start_datetime)
        if end:
            end_datetime = datetime.fromisoformat(end)
            query = query.filter(Email.created_at <= end_datetime)
        if email_from:
            query = query.filter(Email.email_from == email_from)
        if  to:
            query = query.filter(Email.to == to)
        if state:
            query = query.filter(Email.status == state)
        if only_malicious is True:
            query = query.filter(Email.malicious == True)

        query = query.limit(limit).offset(offset)
        emails = query.all()
        email_list = []
        
        for email in emails:
            email_list.append(email.to_dict())
        
        return email_list, 200
    except Exception as e:
         return jsonify({'error': 'An unknown error occurred trying to procress the request: {}'.format(str(e))}), 500
    

@api.route('/customers/<string:customer_id>/emails/<string:id>', methods=['GET'])
def get_email(customer_id, id):
    try:
        # Body/Path parameter was malformed or invalid
        if not is_uuid(customer_id) or not is_uuid(id):
            return jsonify({'error': 'Customer ID is not a valid UUID'}), 400
        
        email = Email.query.filter_by(customer_id=customer_id, id=id).first()
        # The requested email for the customer does not exist.
        if email is None: 
            return jsonify({'error': 'The requested email for the customer does not exist.'}), 404 
        
        return jsonify(email.to_dict()), 200
    
    except Exception as e:
        # An unknown error occurred trying to process the request.
        return jsonify({'error': 'An unknown error occurred trying to procress the request: {}'.format(str(e))}), 500


@api.route('/customers/<string:customer_id>/emails', methods=['POST'])
def create_email(customer_id):
    try:
        # Body/Path parameter was malformed or invalid
        if not is_uuid(customer_id):
            return jsonify({'error': 'Customer ID is not a valid UUID'}), 400

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
        # An unknown error occurred trying to process the request.
         return jsonify({'error': 'An unknown error occurred trying to procress the request: {}'.format(str(e))}), 500

@api.route('/customers/<string:customer_id>/reports/actors', methods=['GET'])
def get_actors(customer_id):
    try:
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
        # An unknown error occurred trying to process the request.
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

        report = {
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'total': len(domains_data),
            'data': domains_data
        }

        return jsonify(report), 200
    
    except Exception as e:
        # An unknown error occurred trying to process the request.
         return jsonify({'error': 'An unknown error occurred trying to procress the request: {}'.format(str(e))}), 500


@api.route('/customers/<string:customer_id>/reports/recipients', methods=['GET'])
def get_recipients(customer_id):
    try:
        recipients = Email.query.filter_by(customer_id=customer_id, malicious=True).group_by(Email.to).all()
        
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
        # An unknown error occurred trying to process the request.
         return jsonify({'error': 'An unknown error occurred trying to procress the request: {}'.format(str(e))}), 500

@api.route('/health') 
def health():
    try:
        return jsonify({'status': 'Service is healthy'}), 200
    except Exception as e:
        return jsonify({'error': 'Service is not healthy: {}'.format(str(e))}), 500