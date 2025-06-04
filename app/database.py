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
            'database': Config.MYSQL_DATABASE,
            'autocommit': False,
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci'
        }
        
        # Configuración para conexión sin base de datos (para crearla)
        self.config_no_db = {
            'host': Config.MYSQL_HOST,
            'port': Config.MYSQL_PORT,
            'user': Config.MYSQL_USER,
            'password': Config.MYSQL_PASSWORD,
            'autocommit': False,
            'charset': 'utf8mb4'
        }

    def test_connection(self):
        """Probar la conexión a MySQL sin especificar base de datos"""
        try:
            conn = mysql.connector.connect(**self.config_no_db)
            if conn.is_connected():
                print(f"✅ Conexión exitosa a MySQL Server en {Config.MYSQL_HOST}:{Config.MYSQL_PORT}")
                conn.close()
                return True
        except Error as e:
            print(f"❌ Error al conectar a MySQL: {e}")
            return False
        return False

    def database_exists(self):
        """Verificar si la base de datos existe"""
        try:
            with mysql.connector.connect(**self.config_no_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SHOW DATABASES LIKE %s", (Config.MYSQL_DATABASE,))
                result = cursor.fetchone()
                exists = result is not None
                print(f"🔍 Base de datos '{Config.MYSQL_DATABASE}': {'Existe' if exists else 'No existe'}")
                return exists
        except Error as e:
            print(f"❌ Error al verificar base de datos: {e}")
            return False

    def create_database(self):
        """Crear la base de datos si no existe"""
        try:
            with mysql.connector.connect(**self.config_no_db) as conn:
                cursor = conn.cursor()
                
                # Crear la base de datos
                cursor.execute(f"""
                    CREATE DATABASE IF NOT EXISTS {Config.MYSQL_DATABASE} 
                    CHARACTER SET utf8mb4 
                    COLLATE utf8mb4_unicode_ci
                """)
                
                print(f"✅ Base de datos '{Config.MYSQL_DATABASE}' creada exitosamente")
                conn.commit()
                return True
        except Error as e:
            print(f"❌ Error al crear base de datos: {e}")
            return False

    @contextmanager
    def get_connection(self):
        """Obtener una conexión a la base de datos usando context manager"""
        conn = None
        try:
            conn = mysql.connector.connect(**self.config)
            yield conn
        except Error as e:
            print(f"❌ Error al conectar a MySQL: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def execute_query(self, query, params=None, fetch_all=True):
        """Ejecutar una consulta y devolver los resultados"""
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(query, params or ())
                
                if query.strip().upper().startswith('SELECT'):
                    return cursor.fetchall() if fetch_all else cursor.fetchone()
                else:
                    conn.commit()
                    return cursor.lastrowid
            except Error as e:
                conn.rollback()
                print(f"❌ Error ejecutando query: {e}")
                print(f"Query: {query}")
                raise
            finally:
                cursor.close()

    def execute_many(self, query, params_list):
        """Ejecutar una consulta múltiples veces con diferentes parámetros"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount
            except Error as e:
                conn.rollback()
                print(f"❌ Error ejecutando query múltiple: {e}")
                raise
            finally:
                cursor.close()

    def execute_script(self, script_path):
        """Ejecutar un script SQL desde archivo"""
        if not os.path.exists(script_path):
            print(f"❌ Archivo de script no encontrado: {script_path}")
            return False

        try:
            with open(script_path, 'r', encoding='utf-8') as file:
                script_content = file.read()

            # Limpiar y procesar el script
            # Remover comentarios y líneas vacías
            lines = []
            for line in script_content.split('\n'):
                line = line.strip()
                if line and not line.startswith('--'):
                    lines.append(line)
            
            # Unir todas las líneas y dividir por ';'
            clean_script = ' '.join(lines)
            commands = [cmd.strip() for cmd in clean_script.split(';') if cmd.strip()]
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for command in commands:
                    # Solo ejecutar comandos SQL válidos
                    if any(command.upper().startswith(prefix) for prefix in 
                          ['CREATE', 'INSERT', 'UPDATE', 'DELETE', 'ALTER', 'DROP', 'SET', 'START', 'COMMIT']):
                        try:
                            cursor.execute(command)
                            # Mostrar mensaje más descriptivo
                            if command.upper().startswith('CREATE TABLE'):
                                table_name = command.split()[5] if len(command.split()) > 5 else "tabla"
                                print(f"✅ Tabla creada: {table_name}")
                            else:
                                print(f"✅ Ejecutado: {command[:50]}...")
                        except Error as e:
                            print(f"⚠️ Advertencia en comando: {e}")
                            print(f"   Comando: {command[:100]}...")
                            # Continuar con el siguiente comando en caso de errores menores
                            continue
                
                conn.commit()
                print("✅ Script ejecutado exitosamente")
                return True

        except Exception as e:
            print(f"❌ Error ejecutando script: {e}")
            return False

    def init_database(self):
        """Inicializar la base de datos completa"""
        print("🚀 Iniciando configuración de base de datos...")
        
        # 1. Probar conexión
        if not self.test_connection():
            print("❌ No se puede conectar a MySQL. Verifica la configuración.")
            return False
        
        # 2. Crear base de datos si no existe
        if not self.database_exists():
            if not self.create_database():
                return False
        
        # 3. Verificar si las tablas ya existen
        if self.tables_exist():
            print("ℹ️ Las tablas ya existen en la base de datos")
            return True
        
        # 4. Ejecutar schema.sql
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if self.execute_script(schema_path):
            print("✅ Base de datos inicializada correctamente")
            return True
        else:
            print("❌ Error al inicializar la base de datos")
            return False

    def tables_exist(self):
        """Verificar si las tablas principales existen"""
        required_tables = [
            'informacion_contacto', 'carrera', 'seccion', 'periodo_academico',
            'alumno', 'profesor', 'autenticacion', 'matricula', 'clase',
            'asistencia', 'registro_facial', 'profesor_clase', 'alumno_clase',
            # Nuevas tablas para funcionalidades de alta prioridad
            'permisos', 'roles', 'rol_permisos', 'usuario_roles',
            'logs_auditoria', 'login_attempts', 'sesiones_activas',
            'configuraciones', 'notificaciones', 'reportes_programados',
            'historial_reportes', 'alertas_sistema'
        ]
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SHOW TABLES")
                existing_tables = [table[0] for table in cursor.fetchall()]
                
                missing_tables = set(required_tables) - set(existing_tables)
                
                if missing_tables:
                    print(f"⚠️ Tablas faltantes: {', '.join(missing_tables)}")
                    return False
                else:
                    print("✅ Todas las tablas requeridas existen")
                    return True
                    
        except Error as e:
            print(f"❌ Error verificando tablas: {e}")
            return False

    def get_db_info(self):
        """Obtener información de la base de datos"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Información del servidor
                cursor.execute("SELECT VERSION() as version")
                version = cursor.fetchone()
                
                # Número de tablas
                cursor.execute("SHOW TABLES")
                tables_count = len(cursor.fetchall())
                
                return {
                    'version': version[0] if version else 'Desconocida',
                    'database': Config.MYSQL_DATABASE,
                    'host': Config.MYSQL_HOST,
                    'port': Config.MYSQL_PORT,
                    'tables_count': tables_count
                }
        except Error as e:
            print(f"❌ Error obteniendo información de BD: {e}")
            return None

    def reset_database(self):
        """CUIDADO: Eliminar y recrear la base de datos completa"""
        try:
            with mysql.connector.connect(**self.config_no_db) as conn:
                cursor = conn.cursor()
                
                # Eliminar base de datos
                cursor.execute(f"DROP DATABASE IF EXISTS {Config.MYSQL_DATABASE}")
                print(f"🗑️ Base de datos '{Config.MYSQL_DATABASE}' eliminada")
                
                conn.commit()
                
                # Recrear base de datos
                return self.init_database()
                
        except Error as e:
            print(f"❌ Error reseteando base de datos: {e}")
            return False

# Instancia global de la base de datos
db = Database()

def init_app(app):
    """Inicializar la aplicación con la base de datos"""
    print(f"🔧 Configurando base de datos MySQL...")
    print(f"   Host: {Config.MYSQL_HOST}:{Config.MYSQL_PORT}")
    print(f"   Database: {Config.MYSQL_DATABASE}")
    print(f"   User: {Config.MYSQL_USER}")
    
    # Inicializar la base de datos automáticamente
    if not db.init_database():
        print("❌ ADVERTENCIA: No se pudo inicializar la base de datos")
        print("   La aplicación puede no funcionar correctamente")
    else:
        # Mostrar información de la base de datos
        info = db.get_db_info()
        if info:
            print(f"📊 Información de la base de datos:")
            print(f"   MySQL Version: {info['version']}")
            print(f"   Tablas creadas: {info['tables_count']}")
    
    # Registrar función de limpieza (no necesaria para MySQL pero mantenemos consistencia)
    @app.teardown_appcontext
    def close_db(error):
        pass  # Las conexiones MySQL se manejan automáticamente con context managers

def get_db():
    """Función helper para compatibilidad con el código existente"""
    return db.get_connection()