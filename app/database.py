import sqlite3
import os
from .config import Config

class Database:
    def __init__(self):
        self.db_path = Config.DATABASE_PATH

    def get_connection(self):
        """Obtener una conexión a la base de datos"""
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Inicializar la base de datos con todas las tablas necesarias"""
        with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), 'r') as f:
            schema = f.read()

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Ejecutar el schema completo
            cursor.executescript(schema)
            conn.commit()
            print(f"Base de datos inicializada correctamente en '{self.db_path}'")
        except sqlite3.Error as e:
            print(f"Error al inicializar la base de datos: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_db(self):
        """Obtener una conexión a la base de datos con control de contexto"""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()

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