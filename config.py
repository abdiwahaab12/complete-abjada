import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

def _mysql_uri():
    """Build MySQL URI from env or use DATABASE_URL. Database: tailor_db."""
    if os.environ.get('DATABASE_URL'):
        return os.environ.get('DATABASE_URL')
    user = os.environ.get('MYSQL_USER', 'root')
    password = os.environ.get('MYSQL_PASSWORD', '')
    host = os.environ.get('MYSQL_HOST', 'localhost')
    port = os.environ.get('MYSQL_PORT', '3306')
    database = os.environ.get('MYSQL_DATABASE', 'tailor_db')
    password_part = f':{password}' if password else ''
    return f'mysql+pymysql://{user}{password_part}@{host}:{port}/{database}'

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tailor-secret-key-change-in-production'
    # MySQL database: tailor_db (set DATABASE_URL or MYSQL_* in .env)
    SQLALCHEMY_DATABASE_URI = _mysql_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
