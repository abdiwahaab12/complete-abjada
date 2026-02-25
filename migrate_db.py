"""
One-time migration: add missing columns to existing MySQL tables
so they match the current models. Safe to run multiple times.
"""
import pymysql

# Columns to add to users if missing (name, type, default)
USERS_ADD_COLUMNS = [
    ("email_verified", "TINYINT(1) DEFAULT 0", None),
    ("verification_token", "VARCHAR(100)", None),
    ("verification_token_expires", "DATETIME", None),
    ("failed_login_attempts", "INT DEFAULT 0", None),
    ("account_locked_until", "DATETIME", None),
    ("last_login_at", "DATETIME", None),
    ("last_login_ip", "VARCHAR(45)", None),
    ("current_login_at", "DATETIME", None),
    ("current_login_ip", "VARCHAR(45)", None),
    ("login_count", "INT DEFAULT 0", None),
    ("full_name", "VARCHAR(120)", None),
    ("phone", "VARCHAR(20)", None),
    ("profile_image", "VARCHAR(255)", None),
    ("created_at", "DATETIME", None),
    ("updated_at", "DATETIME", None),
    ("reset_token", "VARCHAR(100)", None),
    ("reset_token_expires", "DATETIME", None),
    ("refresh_token", "VARCHAR(255)", None),
]


def run_migrate(uri):
    """Add missing columns. uri = SQLAlchemy database URI (mysql+pymysql://...)."""
    if not uri or not uri.startswith("mysql"):
        return
    from sqlalchemy.engine.url import make_url
    u = make_url(uri)
    try:
        conn = pymysql.connect(
            host=u.host or "localhost",
            user=u.username,
            password=u.password or None,
            port=u.port or 3306,
            database=u.database,
        )
    except Exception as e:
        print(f"Migration skip (cannot connect): {e}")
        return
    dup_col = 1060  # MySQL: Duplicate column name
    try:
        with conn.cursor() as cur:
            for col_name, col_def, _ in USERS_ADD_COLUMNS:
                try:
                    cur.execute(f"ALTER TABLE `users` ADD COLUMN `{col_name}` {col_def}")
                    conn.commit()
                    print(f"  + users.{col_name}")
                except pymysql.err.OperationalError as e:
                    conn.rollback()
                    if e.args[0] != dup_col:
                        raise
            # notifications.user_id (if table exists)
            try:
                cur.execute("ALTER TABLE `notifications` ADD COLUMN `user_id` INT NULL")
                conn.commit()
                print("  + notifications.user_id")
            except pymysql.err.OperationalError as e:
                conn.rollback()
                if e.args[0] not in (dup_col, 1146):  # 1146 = table doesn't exist
                    raise
            # Create banks table if missing
            try:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS `banks` (
                        `id` INT NOT NULL AUTO_INCREMENT,
                        `account_number` VARCHAR(40) NOT NULL,
                        `name` VARCHAR(120) NOT NULL,
                        `balance` FLOAT DEFAULT 0,
                        `user_id` INT NULL,
                        `created_at` DATETIME NULL,
                        PRIMARY KEY (`id`),
                        UNIQUE (`account_number`),
                        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
                    )
                """)
                conn.commit()
                print("  + banks table (if created)")
            except pymysql.err.OperationalError as e:
                conn.rollback()
                if e.args[0] != 1050:  # 1050 = table already exists
                    raise
            # Add user_id column to banks if missing
            try:
                cur.execute("ALTER TABLE `banks` ADD COLUMN `user_id` INT NULL")
                conn.commit()
                print("  + banks.user_id")
            except pymysql.err.OperationalError as e:
                conn.rollback()
                if e.args[0] != dup_col:
                    raise
        conn.close()
    except Exception as e:
        conn.close()
        raise
