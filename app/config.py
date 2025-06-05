import os
from dotenv import load_dotenv
from datetime import timedelta

# Cargar variables de entorno desde .env
load_dotenv()

# Configuración base
class Config:
    # Directorio base de la aplicación
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Directorio para datos
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    
    # Asegurarse de que el directorio data existe
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Configuración de base de datos
    DB_TYPE = os.getenv('DB_TYPE', 'mysql')  # 'mysql' o 'sqlite'
    
    # Configuración SQLite (legacy)
    DATABASE_NAME = 'asistencia.db'
    DATABASE_PATH = os.path.join(DATA_DIR, DATABASE_NAME)
    
    # Configuración MySQL
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'elcrepublica')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'asistencia_duoc')
    
    # Clave secreta para la aplicación
    SECRET_KEY = os.getenv('SECRET_KEY', 'clave-secreta')
    
    # Configuración de la aplicación
    UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max-limit
    
    # Asegurarse de que el directorio de uploads existe
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Configuración de Flask-Session
    SESSION_TYPE = 'filesystem'  # Usar sistema de archivos para almacenar sesiones
    SESSION_FILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'flask_session')
    SESSION_FILE_THRESHOLD = 500  # Número máximo de archivos de sesión
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)  # Duración de la sesión
    
    # Asegurarse de que el directorio de sesiones existe
    os.makedirs(SESSION_FILE_DIR, exist_ok=True)

    @classmethod
    def init_app(cls):
        """Inicializar configuraciones y directorios necesarios"""
        # Asegurarse de que los directorios existan
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        
        # Imprimir rutas para debugging
        print(f"Directorio de datos: {cls.DATA_DIR}")
        print(f"Ruta de la base de datos: {cls.DATABASE_PATH}")
        print(f"Directorio de uploads: {cls.UPLOAD_FOLDER}")