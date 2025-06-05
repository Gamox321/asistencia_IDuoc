from flask_login import UserMixin
from .database import db
from datetime import datetime

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.usuario = user_data['usuario']
        self.nombre = user_data.get('nombre', '')
        self.apellido_paterno = user_data.get('apellido_paterno', '')
        self.tipo_usuario = user_data.get('tipo_usuario', 'profesor')
        self.nombre_completo = f"{self.nombre} {self.apellido_paterno}".strip()

    @property
    def is_admin(self):
        return self.tipo_usuario == 'admin'

    @property
    def is_coordinator(self):
        return self.tipo_usuario == 'coordinador'

    @staticmethod
    def get(user_id):
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                cursor.execute("""
                    SELECT a.*, p.nombre, p.apellido_paterno
                    FROM autenticacion a
                    JOIN profesores p ON a.id = p.id
                    WHERE a.id = %s
                """, (user_id,))
                user_data = cursor.fetchone()
                if user_data:
                    print(f"User data loaded: {user_data}")  # Debug print
                    return User(user_data)
                return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None

    def get_id(self):
        return str(self.id)

class Profesor:
    def __init__(self, id, nombre, apellido_paterno, apellido_materno, usuario, estado='activo'):
        self.id = id
        self.nombre = nombre
        self.apellido_paterno = apellido_paterno
        self.apellido_materno = apellido_materno
        self.usuario = usuario
        self.estado = estado

    @staticmethod
    def get_by_id(profesor_id):
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                cursor.execute("""
                    SELECT * FROM profesor 
                    WHERE id = %s
                """, (profesor_id,))
                data = cursor.fetchone()
                if data:
                    return Profesor(**data)
                return None
        except Exception as e:
            print(f"Error getting profesor: {e}")
            return None

class Alumno:
    def __init__(self, id, nombre, apellido_paterno, apellido_materno, rut, estado='activo'):
        self.id = id
        self.nombre = nombre
        self.apellido_paterno = apellido_paterno
        self.apellido_materno = apellido_materno
        self.rut = rut
        self.estado = estado

    @staticmethod
    def get_by_id(alumno_id):
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                cursor.execute("""
                    SELECT * FROM alumno 
                    WHERE id = %s
                """, (alumno_id,))
                data = cursor.fetchone()
                if data:
                    return Alumno(**data)
                return None
        except Exception as e:
            print(f"Error getting alumno: {e}")
            return None

class Clase:
    def __init__(self, id, nombre, profesor_id, horario, estado='activo'):
        self.id = id
        self.nombre = nombre
        self.profesor_id = profesor_id
        self.horario = horario
        self.estado = estado

    @staticmethod
    def get_by_id(clase_id):
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                cursor.execute("""
                    SELECT * FROM clase 
                    WHERE id = %s
                """, (clase_id,))
                data = cursor.fetchone()
                if data:
                    return Clase(**data)
                return None
        except Exception as e:
            print(f"Error getting clase: {e}")
            return None

class Asistencia:
    def __init__(self, id=None, alumno_id=None, clase_id=None, fecha=None, hora=None, presente=False):
        self.id = id
        self.alumno_id = alumno_id
        self.clase_id = clase_id
        self.fecha = fecha or datetime.now().date()
        self.hora = hora or datetime.now().time()
        self.presente = presente

    def save(self):
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor()
                if self.id:
                    # Update
                    cursor.execute("""
                        UPDATE asistencia 
                        SET alumno_id = %s, clase_id = %s, fecha = %s, hora = %s, presente = %s
                        WHERE id = %s
                    """, (self.alumno_id, self.clase_id, self.fecha, self.hora, self.presente, self.id))
                else:
                    # Insert
                    cursor.execute("""
                        INSERT INTO asistencia (alumno_id, clase_id, fecha, hora, presente)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (self.alumno_id, self.clase_id, self.fecha, self.hora, self.presente))
                    self.id = cursor.lastrowid
                conexion.commit()
                return True
        except Exception as e:
            print(f"Error saving asistencia: {e}")
            return False

    @staticmethod
    def get_by_id(asistencia_id):
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                cursor.execute("""
                    SELECT * FROM asistencia 
                    WHERE id = %s
                """, (asistencia_id,))
                data = cursor.fetchone()
                if data:
                    return Asistencia(**data)
                return None
        except Exception as e:
            print(f"Error getting asistencia: {e}")
            return None 