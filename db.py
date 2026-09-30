from sqlalchemy import create_engine, text

server_name = "@UNKNOWN\\SQLEXPRESS"
db_name = "anime_db"
driver = "ODBC+Driver+18+for+SQL+Server"

connection_string = (
    f"mssql+pyodbc://{server_name}/{db_name}"
    f"?driver={driver}"
    "&trusted_connection=yes"
    "&TrustServerCertificate=yes"
)

engine = create_engine(connection_string)

with engine.begin() as conn:
    conn.execute(
        text("""
             IF NOT EXISTS (
                 SELECT 1 FROM sys.schemas
                 WHERE name = 'bronze'
             )
             EXEC('CREATE SCHEMA bronze')
             """)
    )
    conn.execute(
        text("""
             IF NOT EXISTS (
                 SELECT 1 FROM sys.schemas
                 WHERE name = 'silver'
             )
             EXEC('CREATE SCHEMA silver')
             """)
    )
    conn.execute(
        text("""
             IF NOT EXISTS (
                 SELECT 1 FROM sys.schemas
                 WHERE name = 'gold'
             )
             EXEC('CREATE SCHEMA gold')
             """)
    )