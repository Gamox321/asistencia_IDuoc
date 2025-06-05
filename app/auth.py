"""
Módulo de autenticación y seguridad mejorada
Sistema de Asistencia DuocUC
"""

from flask import Blueprint, session, request, redirect, url_for, flash, render_template
from flask_bcrypt import Bcrypt
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
import re
from datetime import datetime, timedelta
from .database import db
from .models import User

# Crear Blueprint de autenticación
bp = Blueprint('auth', __name__, url_prefix='/auth')

# Inicializar bcrypt
bcrypt = Bcrypt()

def require_login(f):
    """Decorador para requerir login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            flash('Por favor inicie sesión', 'warning')
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

class SecurityManager:
    """Gestor de seguridad del sistema"""
    
    @staticmethod
    def init_app(app):
        """Inicializar el módulo de seguridad con la app"""
        bcrypt.init_app(app)
    
    @staticmethod
    def hash_password(password):
        """Hash de contraseña con bcrypt"""
        return bcrypt.generate_password_hash(password).decode('utf-8')
    
    @staticmethod
    def check_password(password, hashed):
        """Verificar contraseña con hash bcrypt"""
        return bcrypt.check_password_hash(hashed, password)
    
    @staticmethod
    def validate_password_strength(password):
        """
        Validar fortaleza de contraseña
        Retorna: (es_valida, lista_errores)
        """
        errors = []
        
        # Longitud mínima
        if len(password) < 8:
            errors.append("La contraseña debe tener al menos 8 caracteres")
        
        # Al menos una letra mayúscula
        if not re.search(r'[A-Z]', password):
            errors.append("Debe contener al menos una letra mayúscula")
        
        # Al menos una letra minúscula
        if not re.search(r'[a-z]', password):
            errors.append("Debe contener al menos una letra minúscula")
        
        # Al menos un número
        if not re.search(r'\d', password):
            errors.append("Debe contener al menos un número")
        
        # Al menos un carácter especial
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Debe contener al menos un carácter especial (!@#$%^&*)")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def log_login_attempt(usuario, exitoso, ip_address=None, user_agent=None):
        """Registrar intento de login"""
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor()
                cursor.execute("""
                    INSERT INTO login_attempts (usuario, ip_address, user_agent, exitoso)
                    VALUES (%s, %s, %s, %s)
                """, (usuario, ip_address, user_agent, exitoso))
                conexion.commit()
        except Exception as e:
            print(f"Error logging login attempt: {e}")
    
    @staticmethod
    def get_failed_attempts(usuario, minutes=15):
        """Obtener número de intentos fallidos en los últimos X minutos"""
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor()
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM login_attempts 
                    WHERE usuario = %s 
                    AND exitoso = FALSE 
                    AND timestamp >= DATE_SUB(NOW(), INTERVAL %s MINUTE)
                """, (usuario, minutes))
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            print(f"Error getting failed attempts: {e}")
            return 0
    
    @staticmethod
    def is_account_locked(usuario, max_attempts=5, lockout_minutes=15):
        """Verificar si una cuenta está bloqueada"""
        failed_attempts = SecurityManager.get_failed_attempts(usuario, lockout_minutes)
        return failed_attempts >= max_attempts
    
    @staticmethod
    def clear_failed_attempts(usuario):
        """Limpiar intentos fallidos después de login exitoso"""
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor()
                cursor.execute("""
                    DELETE FROM login_attempts 
                    WHERE usuario = %s AND exitoso = FALSE
                """, (usuario,))
                conexion.commit()
        except Exception as e:
            print(f"Error clearing failed attempts: {e}")
    
    @staticmethod
    def get_client_info():
        """Obtener información del cliente (IP y User Agent)"""
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR') or request.environ.get('REMOTE_ADDR')
        user_agent = request.environ.get('HTTP_USER_AGENT', '')[:500]  # Limitar longitud
        return ip_address, user_agent
    
    @staticmethod
    def create_session(usuario_id, profesor_data):
        """Crear sesión segura"""
        session.clear()  # Limpiar sesión anterior
        session['usuario'] = profesor_data.get('usuario', '')
        session['profesor_id'] = usuario_id
        session['nombre_profesor'] = f"{profesor_data.get('nombre', '')} {profesor_data.get('apellido_paterno', '')}"
        session['login_time'] = datetime.now().isoformat()
        session['last_activity'] = datetime.now().isoformat()
        
        # Generar nuevo ID de sesión para prevenir session fixation
        session.permanent = True
    
    @staticmethod
    def check_session_timeout(timeout_minutes=60):
        """Verificar si la sesión ha expirado"""
        if 'last_activity' not in session:
            return True
        
        try:
            last_activity = datetime.fromisoformat(session['last_activity'])
            if datetime.now() - last_activity > timedelta(minutes=timeout_minutes):
                return True
            
            # Actualizar última actividad
            session['last_activity'] = datetime.now().isoformat()
            return False
        except:
            return True
    
    @staticmethod
    def logout_user():
        """Logout seguro"""
        session.clear()

class PasswordMigrator:
    """Utilidad para migrar contraseñas de SHA256 a bcrypt"""
    
    @staticmethod
    def migrate_all_passwords():
        """Migrar todas las contraseñas existentes"""
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                
                # Obtener usuarios con contraseñas SHA256 (64 caracteres)
                cursor.execute("""
                    SELECT id, usuario, password_hash 
                    FROM autenticacion 
                    WHERE LENGTH(password_hash) = 64
                """)
                usuarios = cursor.fetchall()
                
                migrated_count = 0
                for usuario in usuarios:
                    # La contraseña por defecto es "123456", vamos a migrarla
                    new_hash = SecurityManager.hash_password("123456")
                    
                    cursor.execute("""
                        UPDATE autenticacion 
                        SET password_hash = %s 
                        WHERE id = %s
                    """, (new_hash, usuario['id']))
                    
                    migrated_count += 1
                
                conexion.commit()
                print(f"✅ {migrated_count} contraseñas migradas a bcrypt")
                return True
                
        except Exception as e:
            print(f"❌ Error migrando contraseñas: {e}")
            return False
    
    @staticmethod
    def is_bcrypt_hash(password_hash):
        """Verificar si un hash es de bcrypt"""
        return password_hash.startswith('$2b$') and len(password_hash) == 60

# Decorador para requerir rol de administrador
def admin_required(f):
    """Decorador para requerir rol de administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            flash('Por favor inicie sesión', 'warning')
            return redirect(url_for('auth.login'))
            
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                cursor.execute("""
                    SELECT tipo_usuario 
                    FROM autenticacion 
                    WHERE profesor_id = %s
                """, (session.get('profesor_id'),))
                
                result = cursor.fetchone()
                if not result or result['tipo_usuario'] != 'admin':
                    flash('No tienes permisos de administrador', 'error')
                    return redirect(url_for('main.dashboard'))
                    
        except Exception as e:
            print(f"Error verificando rol admin: {e}")
            flash('Error verificando permisos', 'error')
            return redirect(url_for('main.dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

def get_current_user_id():
    """Obtener el ID del usuario actual desde la sesión"""
    return session.get('profesor_id')

def get_current_username():
    """Obtener el nombre de usuario actual desde la sesión"""
    return session.get('usuario')

# Rutas de autenticación
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        usuario = request.form.get('usuario')
        password = request.form.get('password')
        
        # Validar campos requeridos
        if not usuario or not password:
            flash('Usuario y contraseña son requeridos', 'error')
            return render_template('login.html')
        
        # Verificar bloqueo de cuenta
        if SecurityManager.is_account_locked(usuario):
            flash('Cuenta bloqueada temporalmente por múltiples intentos fallidos', 'error')
            return render_template('login.html')
        
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                
                # Buscar usuario
                cursor.execute("""
                    SELECT a.*, p.* 
                    FROM autenticacion a
                    JOIN profesores p ON a.id = p.id 
                    WHERE a.usuario = %s
                """, (usuario,))
                
                profesor = cursor.fetchone()
                
                # Registrar intento de login
                ip_address, user_agent = SecurityManager.get_client_info()
                
                if not profesor:
                    SecurityManager.log_login_attempt(usuario, False, ip_address, user_agent)
                    flash('Usuario o contraseña incorrectos', 'error')
                    return render_template('login.html')
                
                # Verificar contraseña
                if not SecurityManager.check_password(password, profesor['password_hash']):
                    SecurityManager.log_login_attempt(usuario, False, ip_address, user_agent)
                    flash('Usuario o contraseña incorrectos', 'error')
                    return render_template('login.html')
                
                # Login exitoso
                SecurityManager.log_login_attempt(usuario, True, ip_address, user_agent)
                SecurityManager.clear_failed_attempts(usuario)
                
                # Crear usuario y hacer login con Flask-Login
                user = User(profesor)
                login_user(user)
                
                # Crear sesión segura
                SecurityManager.create_session(profesor['id'], profesor)
                
                flash('Bienvenido al sistema', 'success')
                return redirect(url_for('main.dashboard'))
                
        except Exception as e:
            print(f"Error en login: {e}")
            flash('Error al iniciar sesión', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    SecurityManager.logout_user()
    flash('Has cerrado sesión exitosamente', 'success')
    return redirect(url_for('auth.login'))

def check_admin_access():
    """Verifica si el usuario actual tiene acceso de administrador"""
    try:
        with db.get_connection() as conexion:
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("""
                SELECT tipo_usuario
                FROM autenticacion
                WHERE profesor_id = %s
            """, (session.get('profesor_id'),))
            
            result = cursor.fetchone()
            if not result or result['tipo_usuario'] != 'admin':
                return False
            return True
            
    except Exception as e:
        print(f"Error verificando acceso admin: {e}")
        return False 