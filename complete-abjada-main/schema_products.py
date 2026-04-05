"""
Rename legacy table `inventory` -> `products` so SQL like SELECT * FROM products works.
Safe to run multiple times. Runs before db.create_all().
"""
from sqlalchemy import inspect, text


def rename_inventory_to_products_if_needed(engine):
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
    except Exception as e:
        print(f"[schema_products] inspect skip: {e}")
        return

    if "products" in tables:
        return
    if "inventory" not in tables:
        return

    dialect = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dialect == "sqlite":
                conn.execute(text("ALTER TABLE inventory RENAME TO products"))
            else:
                conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                conn.execute(text("RENAME TABLE inventory TO products"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        print("[schema_products] Renamed table inventory -> products (use SELECT * FROM products)")
    except Exception as e:
        print(f"[schema_products] Rename failed (fix manually or use backup): {e}")
