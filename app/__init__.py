from flask import Flask
from .config import Config
from .database import init_app
import os

def create_app(test_config=None):
    # Crear la instancia de la aplicación
    app = Flask(__name__, instance_relative_config=True)
    
    if test_config is None:
        # Cargar la configuración por defecto
        app.config.from_object(Config)
        # Inicializar configuraciones
        Config.init_app()
    else:
        # Cargar la configuración de prueba si se proporciona
        app.config.update(test_config)

    # Asegurar que existe el directorio de la instancia
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Asegurar que existe el directorio de uploads
    try:
        os.makedirs(Config.UPLOAD_FOLDER)
    except OSError:
        pass

    # Inicializar la base de datos
    init_app(app)

    # Configurar la clave secreta para las sesiones
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = os.urandom(24)

    # Registrar el Blueprint principal
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    # Registrar manejadores de errores personalizados
    @app.errorhandler(404)
    def page_not_found(e):
        return {"error": "Página no encontrada"}, 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return {"error": "Error interno del servidor"}, 500

    # Configurar encabezados de seguridad
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    return app 