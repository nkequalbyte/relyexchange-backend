import os

class Config:
    DEBUG = os.environ.get('FLASK_DEBUG', False)
    DB_HOST = os.environ.get('DB_HOST', 'aws-0-us-east-1.pooler.supabase.com')
    DB_PORT = os.environ.get('DB_PORT', '6543')
    DB_NAME = os.environ.get('DB_NAME', 'postgres')
    DB_USER = os.environ.get('DB_USER', 'postgres.hdesapbxgxecjzfuggjo')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '0oocbYXnrWknAbt7')
