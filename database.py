import pymysql

connection = pymysql.connect(
    host='localhost',
    user='macs',
    password='mypassword123'
)

try:
    with connection.cursor() as cursor:
        cursor.execute("CREATE DATABASE IF NOT EXISTS ict_du_db;")
        print("Database 'ict_du_db' created successfully!")
finally:
    connection.close()