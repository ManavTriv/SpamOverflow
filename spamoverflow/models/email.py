import datetime
import json
from . import db
from sqlalchemy import Enum

class Email(db.Model):
    __tablename__ = 'emails'

    # The email message's unique identifier. This is generated by the email scanning service when the scan request is submitted.
    customer_id = db.Column(db.String(80))
    # The email message's unique identifier. This is generated by the email scanning service when the scan request is submitted.
    id = db.Column(db.String(80), primary_key=True)
    # The date and time the email was submitted.
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    # The date and time the email was updated including its creation.
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # SpamHammer metadata for this email.
    spamhammer = db.Column(db.String(80))
    # The email address to which the email was sent.
    to = db.Column(db.String(80))
    # The email address from which the email was sent.
    email_from = db.Column(db.String(80))
    # The subject of the email.
    subject = db.Column(db.String(120))
    # The status of the email scan.
    status = db.Column(Enum('pending', 'scanned', 'failed', name='email_status'), default='pending')
    # Whether the email was flagged as malicious.
    malicious = db.Column(db.Boolean)
    # The domains of links found within the email body.
    domains = db.Column(db.String(120))

    # This is a helper method to convert the model to a dictionary
    def to_dict(self):
        return {
        'id': self.id,
        'created_at': self.created_at.isoformat() if self.created_at else None,
        'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        'contents': {
                'to': self.to,
                'from': self.email_from,
                'subject': self.subject
            },
        'metadata': {
                'spamhammer': self.spamhammer
            },
        'status': self.status,
        'malicious': self.malicious,
        'domains': self.domains.split(';') if self.domains else []
        }
    
    def __repr__(self):
        return f'<Customer {self.id}>'