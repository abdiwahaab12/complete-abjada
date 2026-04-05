"""Add product_colors table columns on measurements/fabric_usage for existing DBs."""
from sqlalchemy import inspect, text


def apply_product_color_schema_patches(db) -> None:
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

    add_column_sqlite("measurements", "product_color_id INTEGER")
    add_column_mysql("measurements", "`product_color_id` INT NULL")

    add_column_sqlite("measurements", "clothing_type VARCHAR(80)")
    add_column_mysql("measurements", "`clothing_type` VARCHAR(80) NULL")

    add_column_sqlite("fabric_usage", "product_color_id INTEGER")
    add_column_mysql("fabric_usage", "`product_color_id` INT NULL")

    add_column_sqlite("measurements", "fabric_yard_breakdown TEXT")
    add_column_mysql("measurements", "`fabric_yard_breakdown` TEXT NULL")

    add_column_sqlite("products", "price REAL")
    add_column_mysql("products", "`price` DOUBLE NULL")

    add_column_sqlite("products", "color_category VARCHAR(120)")
    add_column_mysql("products", "`color_category` VARCHAR(120) NULL")

    add_column_sqlite("products", "default_yards_per_piece REAL")
    add_column_mysql("products", "`default_yards_per_piece` DOUBLE NULL")
