import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _mysql_uri():
    """
    Build MySQL URI safely.
    Priority:
    1. Use DATABASE_URL if provided
    2. Use MYSQL_* environment variables
    """

    # 1️⃣ Haddii DATABASE_URL jiro isticmaal
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        # Fix for Railway sometimes giving mysql:// instead of mysql+pymysql://
        if database_url.startswith("mysql://"):
            database_url = database_url.replace(
                "mysql://", "mysql+pymysql://", 1
            )
        return database_url

    # 2️⃣ Haddii kale isticmaal MYSQL_* variables
    user = os.environ.get("MYSQL_USER")
    password = os.environ.get("MYSQL_PASSWORD")
    host = os.environ.get("MYSQL_HOST")
    port = os.environ.get("MYSQL_PORT", "3306")
    database = os.environ.get("MYSQL_DATABASE")

    # 🔥 Haddii wax maqan yihiin ha ogolaan app-ku inuu bilaabmo
    if not all([user, password, host, database]):
        raise ValueError(
            "Missing MySQL environment variables. "
            "Please set MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_DATABASE."
        )

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")

    SQLALCHEMY_DATABASE_URI = _mysql_uri()
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