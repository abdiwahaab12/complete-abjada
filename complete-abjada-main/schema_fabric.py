"""Add fabric yard columns and fabric_usage table support on existing DBs."""
from sqlalchemy import inspect, text


def apply_fabric_schema_patches(db) -> None:
    try:
        insp = inspect(db.engine)
    except Exception:
        return

    uri = str(db.engine.url)
    is_sqlite = "sqlite" in uri

    def add_column_sqlite(table: str, coldef: str):
        if not is_sqlite:
            return
        cols = [c["name"] for c in insp.get_columns(table)]
        colname = coldef.split()[0].strip('"').strip("`")
        if colname in cols:
            return
        db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {coldef}"))
        db.session.commit()

    def add_column_mysql(table: str, coldef: str):
        if is_sqlite:
            return
        cols = [c["name"] for c in insp.get_columns(table)]
        colname = coldef.split()[0].strip("`")
        if colname in cols:
            return
        try:
            db.session.execute(text(f"ALTER TABLE `{table}` ADD COLUMN {coldef}"))
            db.session.commit()
        except Exception:
            db.session.rollback()

    add_column_sqlite("products", "total_yards FLOAT DEFAULT 0")
    add_column_mysql("products", "`total_yards` FLOAT DEFAULT 0")

    add_column_sqlite("products", "remaining_yards FLOAT")
    add_column_mysql("products", "`remaining_yards` FLOAT NULL")

    add_column_sqlite("measurements", "product_id INTEGER")
    add_column_mysql("measurements", "`product_id` INT NULL")

    add_column_sqlite("measurements", "fabric_yards FLOAT")
    add_column_mysql("measurements", "`fabric_yards` FLOAT NULL")

    # Backfill remaining_yards from total_yards when null
    try:
        db.session.execute(
            text(
                "UPDATE products SET remaining_yards = total_yards "
                "WHERE remaining_yards IS NULL AND total_yards IS NOT NULL"
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
