import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager
import os
from .config import Config

class Database:
    def __init__(self):
        self.config = {
            'host': Config.MYSQL_HOST,
            'port': Config.MYSQL_PORT,
            'user': Config.MYSQL_USER,
            'password': Config.MYSQL_PASSWORD,
            'database': Config.MYSQL_DATABASE
        }

    @contextmanager
    def get_connection(self):
        """Obtener una conexión a la base de datos usando context manager"""
        conn = None
        try:
            conn = mysql.connector.connect(**self.config)
            yield conn
        except Error as e:
            print(f"Error al conectar a MySQL: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def execute_query(self, query, params=None):
        """Ejecutar una consulta y devolver los resultados"""
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(query, params or ())
                if query.strip().upper().startswith('SELECT'):
                    return cursor.fetchall()
                conn.commit()
                return cursor.lastrowid
            finally:
                cursor.close()

    def execute_many(self, query, params_list):
        """Ejecutar una consulta múltiples veces con diferentes parámetros"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.executemany(query, params_list)
                conn.commit()
            finally:
                cursor.close()

# Instancia global de la base de datos
db = Database()

def init_app(app):
    """Inicializar la aplicación con la base de datos"""
    # Asegurarse de que el directorio de la base de datos existe
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    
    # Inicializar la base de datos si no existe
    if not os.path.exists(Config.DATABASE_PATH):
        db.init_db()
    
    # Registrar función de limpieza
    @app.teardown_appcontext
    def close_db(error):
        pass  # SQLite se cierra automáticamente con el context manager