"""Add finance-related columns on existing SQLite / MySQL databases."""
from sqlalchemy import inspect, text


def apply_finance_schema_patches(db) -> None:
    """Run after db.create_all(). Safe to call multiple times."""
    try:
        insp = inspect(db.engine)
    except Exception:
        return

    uri = str(db.engine.url)
    is_sqlite = 'sqlite' in uri

    def add_column_sqlite(table: str, coldef: str):
        if not is_sqlite:
            return
        cols = [c['name'] for c in insp.get_columns(table)]
        colname = coldef.split()[0].strip('"').strip('`')
        if colname in cols:
            return
        db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN {coldef}'))
        db.session.commit()

    def add_column_mysql(table: str, coldef: str):
        if is_sqlite:
            return
        cols = [c['name'] for c in insp.get_columns(table)]
        colname = coldef.split()[0].strip('`')
        if colname in cols:
            return
        try:
            db.session.execute(text(f'ALTER TABLE `{table}` ADD COLUMN {coldef}'))
            db.session.commit()
        except Exception:
            db.session.rollback()

    add_column_sqlite('orders', "payment_status VARCHAR(20) DEFAULT 'unpaid'")
    add_column_mysql('orders', "`payment_status` VARCHAR(20) DEFAULT 'unpaid'")

    add_column_sqlite('transactions', 'payment_status VARCHAR(20)')
    add_column_mysql('transactions', '`payment_status` VARCHAR(20)')

    add_column_sqlite('transactions', 'account_type VARCHAR(40)')
    add_column_mysql('transactions', '`account_type` VARCHAR(40)')

    add_column_sqlite('transactions', 'counterparty VARCHAR(200)')
    add_column_mysql('transactions', '`counterparty` VARCHAR(200)')

    add_column_sqlite('transactions', 'customer_id INTEGER')
    add_column_mysql('transactions', '`customer_id` INT NULL')

    add_column_sqlite('transactions', 'paid_amount FLOAT')
    add_column_mysql('transactions', '`paid_amount` FLOAT NULL')

    # TransactionCategory.allowed_users (older DBs created before this column)
    add_column_sqlite('transaction_categories', "allowed_users VARCHAR(80) DEFAULT 'all'")
    add_column_mysql('transaction_categories', "`allowed_users` VARCHAR(80) DEFAULT 'all'")

    # Backfill orders.payment_status via ORM (portable)
    try:
        from models import Order
        from finance_logic import sync_order_payment_status
        for o in Order.query.all():
            sync_order_payment_status(o)
        db.session.commit()
    except Exception:
        db.session.rollback()
