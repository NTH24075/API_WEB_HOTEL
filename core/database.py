import os
import pyodbc
from typing import Any
from dotenv import load_dotenv

load_dotenv()

server = os.getenv("DB_SERVER")
database = os.getenv("DB_NAME")
username = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")

def get_conn() -> pyodbc.Connection:
    if username and password:
        conn_str = (
            "Driver={ODBC Driver 17 for SQL Server};"
            f"Server={server};"
            f"Database={database};"
            f"UID={username};"
            f"PWD={password};"
            "TrustServerCertificate=yes;"
        )
    else:
        conn_str = (
            "Driver={ODBC Driver 17 for SQL Server};"
            f"Server=DESKTOP-9S1GU4C\SQLExpress;"
            f"Database=QuanLyKhachSan;"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )

    return pyodbc.connect(conn_str)


def get_db():
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


def query_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    rows = query_all(sql, params)
    return rows[0] if rows else None