import os
import pymysql
from datetime import timedelta
from dotenv import load_dotenv

# Fix MySQLdb driver error
pymysql.install_as_MySQLdb()

load_dotenv()


def _mysql_uri():
    """
    Build MySQL URI for Railway production deployment.
    Priority:
    1. DATABASE_URL
    2. MYSQL_* environment variables
    """

    # Railway default database URL
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return db_url.replace("mysql://", "mysql+pymysql://")

    user = os.environ.get("MYSQLUSER")
    password = os.environ.get("MYSQLPASSWORD")
    host = os.environ.get("MYSQLHOST")
    port = os.environ.get("MYSQLPORT", "3306")
    database = os.environ.get("MYSQLDATABASE")

    if not all([user, password, host, database]):
        raise Exception("Missing MySQL environment variables")

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


class Config:

    # Security keys
    SECRET_KEY = os.environ.get("SECRET_KEY", "tailor-secret-key-change")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change")

    # Database
    SQLALCHEMY_DATABASE_URI = _mysql_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT expiration
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    # Upload folder
    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(__file__),
        "static",
        "uploads"
    )

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # Mail config
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")