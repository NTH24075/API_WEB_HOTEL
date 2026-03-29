import pyodbc

conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=LAPTOP-17TAM013\\SQLEXPRESS;"
    "Database=QuanLyKhachSan;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

def get_conn():
    return pyodbc.connect(conn_str)