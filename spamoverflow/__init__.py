from os import environ
from flask import Flask
 
def create_app(config_overrides=None): 
   app = Flask(__name__) 
 
   return app