import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _default_sqlite_uri():
    """SQLite under instance/local.db when MySQL is not configured."""
    base = os.path.dirname(os.path.abspath(__file__))
    instance_dir = os.path.join(base, "instance")
    os.makedirs(instance_dir, exist_ok=True)
    db_path = os.path.join(instance_dir, "local.db")
    return "sqlite:///" + db_path.replace("\\", "/")


def _database_uri():
    """
    Priority:
    1. DATABASE_URL
    2. MYSQL_USER + MYSQL_HOST + MYSQL_DATABASE (MYSQL_PASSWORD may be empty)
    3. SQLite instance/local.db (local dev without .env)
    """
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        if database_url.startswith("mysql://"):
            database_url = database_url.replace(
                "mysql://", "mysql+pymysql://", 1
            )
        return database_url

    user = os.environ.get("MYSQL_USER")
    password = os.environ.get("MYSQL_PASSWORD", "")
    host = os.environ.get("MYSQL_HOST")
    port = os.environ.get("MYSQL_PORT", "3306")
    database = os.environ.get("MYSQL_DATABASE")

    if user and host and database:
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

    return _default_sqlite_uri()
 

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")

    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-this-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")