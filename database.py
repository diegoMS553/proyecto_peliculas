import mysql.connector

# Configuración de la base de datos
database = mysql.connector.connect(
    host='localhost',
    user='root',
    password='',
    database='movie_database1'
)
