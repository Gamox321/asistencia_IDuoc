"""
Sistema de Roles y Permisos
Sistema de Asistencia DuocUC
"""

from functools import wraps
from flask import session, flash, redirect, url_for, abort
from .database import db
from .auth import require_login, get_current_user_id
from flask import Blueprint, request, render_template
from mysql.connector import Error

class RoleManager:
    """Gestor de roles y permisos del sistema"""
    
    @staticmethod
    def get_user_roles(usuario_id):
        """Obtener roles de un usuario"""
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                cursor.execute("""
                    SELECT r.nombre, r.descripcion, r.nivel_acceso
                    FROM roles r
                    JOIN usuario_roles ur ON r.id = ur.rol_id
                    WHERE ur.usuario_id = %s AND ur.activo = TRUE
                    AND (ur.fecha_expiracion IS NULL OR ur.fecha_expiracion > NOW())
                """, (usuario_id,))
                return cursor.fetchall()
        except Exception as e:
            print(f"Error obteniendo roles: {e}")
            return []
    
    @staticmethod
    def get_user_permissions(usuario_id):
        """Obtener permisos de un usuario"""
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                cursor.execute("""
                    SELECT DISTINCT p.nombre, p.descripcion, p.categoria
                    FROM permisos p
                    JOIN rol_permisos rp ON p.id = rp.permiso_id
                    JOIN usuario_roles ur ON rp.rol_id = ur.rol_id
                    WHERE ur.usuario_id = %s AND ur.activo = TRUE
                    AND (ur.fecha_expiracion IS NULL OR ur.fecha_expiracion > NOW())
                """, (usuario_id,))
                return cursor.fetchall()
        except Exception as e:
            print(f"Error obteniendo permisos: {e}")
            return []
    
    @staticmethod
    def user_has_role(usuario_id, role_name):
        """Verificar si un usuario tiene un rol específico"""
        roles = RoleManager.get_user_roles(usuario_id)
        return any(role['nombre'] == role_name for role in roles)
    
    @staticmethod
    def user_has_permission(usuario_id, permission_name):
        """Verificar si un usuario tiene un permiso específico"""
        permissions = RoleManager.get_user_permissions(usuario_id)
        return any(perm['nombre'] == permission_name for perm in permissions)
    
    @staticmethod
    def get_user_highest_role_level(usuario_id):
        """Obtener el nivel más alto de roles del usuario"""
        roles = RoleManager.get_user_roles(usuario_id)
        if not roles:
            return 0
        return max(role['nivel_acceso'] for role in roles)
    
    @staticmethod
    def is_admin(usuario_id):
        """Verificar si el usuario es administrador"""
        return RoleManager.user_has_role(usuario_id, 'admin')
    
    @staticmethod
    def is_coordinator(usuario_id):
        """Verificar si el usuario es coordinador"""
        return RoleManager.user_has_role(usuario_id, 'coordinador')
    
    @staticmethod
    def is_professor(usuario_id):
        """Verificar si el usuario es profesor"""
        return RoleManager.user_has_role(usuario_id, 'profesor')

# Decoradores para control de acceso
def require_role(role_name):
    """Decorador para requerir un rol específico"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not require_login():
                flash('Debes iniciar sesión', 'error')
                return redirect(url_for('main.login'))
            
            usuario_id = get_current_user_id()
            if not RoleManager.user_has_role(usuario_id, role_name):
                flash(f'No tienes permisos para acceder a esta sección', 'error')
                return redirect(url_for('main.home'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_permission(permission_name):
    """Decorador para requerir un permiso específico"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not require_login():
                flash('Debes iniciar sesión', 'error')
                return redirect(url_for('main.login'))
            
            usuario_id = get_current_user_id()
            if not RoleManager.user_has_permission(usuario_id, permission_name):
                flash(f'No tienes permisos para realizar esta acción', 'error')
                return redirect(url_for('main.home'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_level(min_level):
    """Decorador para requerir un nivel mínimo de acceso"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not require_login():
                flash('Debes iniciar sesión', 'error')
                return redirect(url_for('main.login'))
            
            usuario_id = get_current_user_id()
            user_level = RoleManager.get_user_highest_role_level(usuario_id)
            
            if user_level < min_level:
                flash(f'No tienes el nivel de acceso requerido', 'error')
                return redirect(url_for('main.home'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """Decorador para rutas que requieren admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"DEBUG Admin Required - Checking session: {dict(session)}")
        if 'usuario' not in session:
            print("DEBUG Admin Required - No user in session")
            flash('Por favor inicie sesión', 'warning')
            return redirect(url_for('main.login'))
            
        if not session.get('es_admin'):
            print(f"DEBUG Admin Required - User is not admin. es_admin={session.get('es_admin')}")
            flash('No tienes permisos de administrador', 'error')
            return redirect(url_for('main.home'))
            
        print("DEBUG Admin Required - Access granted")
        return f(*args, **kwargs)
    return decorated_function

def coordinator_required(f):
    """Decorador para rutas que requieren coordinador o admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            flash('Por favor inicie sesión', 'warning')
            return redirect(url_for('main.login'))
            
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                cursor.execute("""
                    SELECT es_coordinador 
                    FROM autenticacion 
                    WHERE id = %s
                """, (session.get('profesor_id'),))
                
                result = cursor.fetchone()
                if not result or not result['es_coordinador']:
                    flash('No tienes permisos de coordinador', 'error')
                    return redirect(url_for('main.home'))
                    
        except Exception as e:
            print(f"Error verificando rol coordinador: {e}")
            flash('Error verificando permisos', 'error')
            return redirect(url_for('main.home'))
            
        return f(*args, **kwargs)
    return decorated_function

def professor_required(f):
    """Decorador para rutas que requieren profesor, coordinador o admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            flash('Por favor inicie sesión', 'warning')
            return redirect(url_for('main.login'))
            
        try:
            profesor_id = session.get('profesor_id')
            if not profesor_id:
                flash('No tienes permisos de profesor', 'error')
                return redirect(url_for('main.dashboard'))
                    
        except Exception as e:
            print(f"Error verificando rol profesor: {e}")
            flash('Error verificando permisos', 'error')
            return redirect(url_for('main.dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

# Funciones helper para usar en templates
def get_user_role_context(user_id):
    """Obtener el contexto de roles del usuario"""
    try:
        with db.get_connection() as conexion:
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    a.tipo_usuario,
                    CASE WHEN a.tipo_usuario = 'admin' THEN TRUE ELSE FALSE END as es_admin,
                    CASE WHEN a.tipo_usuario = 'coordinador' THEN TRUE ELSE FALSE END as es_coordinador,
                    CASE WHEN a.tipo_usuario = 'profesor' THEN TRUE ELSE FALSE END as es_profesor
                FROM autenticacion a
                WHERE a.profesor_id = %s
            """, (user_id,))
            result = cursor.fetchone()
            
            if not result:
                return {'is_admin': False, 'is_coordinator': False, 'is_professor': False}
            
            return {
                'is_admin': result['tipo_usuario'] == 'admin',
                'is_coordinator': result['tipo_usuario'] == 'coordinador',
                'is_professor': result['tipo_usuario'] == 'profesor'
            }
            
    except Exception as e:
        print(f"❌ Error al conectar a MySQL: {str(e)}")
        print(f"Error obteniendo roles: {str(e)}")
        return {'is_admin': False, 'is_coordinator': False, 'is_professor': False} 