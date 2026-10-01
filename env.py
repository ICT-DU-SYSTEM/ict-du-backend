from sqlalchemy import create_engine, text

engine = create_engine(
    "mysql+pymysql://root:@127.0.0.1:3306"
)

with engine.connect() as conn:
    conn.execute(text("""
        CREATE DATABASE IF NOT EXISTS ict_du_ai
        CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci
    """))
    conn.commit()

print("Database ready.")