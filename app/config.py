import os

# Configuración base
class Config:
    # Directorio base de la aplicación
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Directorio para datos
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    
    # Asegurarse de que el directorio data existe
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Ruta de la base de datos (asegurarse de que no se duplique la ruta)
    DATABASE_NAME = 'asistencia.db'
    DATABASE_PATH = os.path.join(DATA_DIR, DATABASE_NAME)
    
    # Clave secreta para la aplicación
    SECRET_KEY = 'clave-secreta'  # En producción, usar variable de entorno
    
    # Configuración de la aplicación
    UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max-limit
    
    # Asegurarse de que el directorio de uploads existe
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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