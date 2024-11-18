import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key')
    GOOGLE_CLOUD_CREDENTIALS_PATH = os.getenv('GOOGLE_CLOUD_CREDENTIALS_PATH')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
