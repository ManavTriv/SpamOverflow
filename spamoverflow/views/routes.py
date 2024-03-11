from flask import Blueprint, jsonify, request
 
api = Blueprint('api', __name__, url_prefix='/api/v1') 
 
@api.route('/health') 
def health():
    """Return a status of 'ok' if the server is running and listening to request"""
    return jsonify({"status": "ok"})