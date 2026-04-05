"""
db.py  —  Kết nối SQL Server (MSSQL) dùng pyodbc.
Thêm các biến sau vào file .env:
    DB_SERVER=localhost
    DB_NAME=QuanLyKhachSan
    DB_USER=sa
    DB_PASSWORD=your_password
    DB_DRIVER=ODBC Driver 17 for SQL Server
"""

import os
import pyodbc
from functools import lru_cache
from typing import Any
from dotenv import load_dotenv

load_dotenv()

_DB_SERVER   = os.getenv("DB_SERVER",   "localhost")
_DB_NAME     = os.getenv("DB_NAME",     "QuanLyKhachSan")
_DB_USER     = os.getenv("DB_USER",     "sa")
_DB_PASSWORD = os.getenv("DB_PASSWORD", "")
_DB_DRIVER   = os.getenv("DB_DRIVER",   "ODBC Driver 17 for SQL Server")


def get_connection() -> pyodbc.Connection:
    """Tạo connection mới tới SQL Server."""
    if _DB_USER and _DB_PASSWORD:
        conn_str = (
            "Driver={ODBC Driver 17 for SQL Server};"
            f"Server={_DB_SERVER};"
            f"Database={_DB_NAME};"
            f"UID={_DB_USER};"
            f"PWD={_DB_PASSWORD};"
            "TrustServerCertificate=yes;"
        )
    else:
        conn_str = (
            "Driver={ODBC Driver 17 for SQL Server};"
            f"Server=DESKTOP-8872D2D;"
            f"Database=QuanLyKhachSan;"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )

    return pyodbc.connect(conn_str, timeout=10)


def query_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Chạy SELECT, trả về list[dict]."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    """Chạy SELECT, trả về dict đầu tiên hoặc None."""
    rows = query_all(sql, params)
    return rows[0] if rows else None


# ── Cache in-memory (tránh query DB mỗi request cho dữ liệu ít thay đổi) ──────

@lru_cache(maxsize=1)
def get_amenity_labels_cached() -> list[dict[str, Any]]:
    """
    Trả về list amenities từ bảng Services.
    Dùng lru_cache — restart app để làm mới cache khi seed data thay đổi.
    """
    return query_all(
        "SELECT ServiceId, ServiceName, IconEmoji, Description "
        "FROM Services WHERE IsActive = 1 ORDER BY ServiceId"
    )


@lru_cache(maxsize=1)
def get_city_aliases_cached() -> dict[str, str]:
    """
    Trả về dict {CityCode: CityName} từ bảng Cities.
    Cột CityCode cần được thêm (xem seed_data.sql).
    """
    rows = query_all(
        "SELECT CityCode, CityName FROM Cities WHERE CityCode IS NOT NULL"
    )
    return {row["CityCode"].upper(): row["CityName"] for row in rows}


def invalidate_cache() -> None:
    """Xóa cache khi cần reload dữ liệu (ví dụ: sau khi admin cập nhật DB)."""
    get_amenity_labels_cached.cache_clear()
    get_city_aliases_cached.cache_clear()