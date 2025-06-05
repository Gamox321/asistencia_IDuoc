#!/usr/bin/env python3
"""
Script para poblar la base de datos MySQL con datos de prueba
Sistema de Asistencia DuocUC - Versión MySQL
"""

import sys
import os
import hashlib
from datetime import datetime, date, timedelta

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import db
from app.config import Config

def crear_datos_prueba():
    """Crear datos de prueba en la base de datos MySQL"""
    
    print("🚀 Iniciando creación de datos de prueba...")
    
    # Verificar conexión
    if not db.test_connection():
        print("❌ No se puede conectar a MySQL")
        return False
    
    # Inicializar base de datos
    if not db.init_database():
        print("❌ Error inicializando base de datos")
        return False
    
    try:
        with db.get_connection() as conexion:
            cursor = conexion.cursor()
            
            # 1. INFORMACIÓN DE CONTACTO
            print("📞 Creando información de contacto...")
            contactos = [
                ('juan.profesor@duoc.cl', '+56912345678', 'Las Condes', 'Santiago'),
                ('maria.docente@duoc.cl', '+56987654321', 'Providencia', 'Santiago'),
                ('carlos.alumno@duocuc.cl', '+56955555555', 'Maipú', 'Santiago'),
                ('ana.estudiante@duocuc.cl', '+56944444444', 'Ñuñoa', 'Santiago'),
                ('pedro.alumno@duocuc.cl', '+56933333333', 'San Miguel', 'Santiago'),
                ('sofia.estudiante@duocuc.cl', '+56922222222', 'La Florida', 'Santiago'),
                ('diego.alumno@duocuc.cl', '+56911111111', 'Puente Alto', 'Santiago'),
            ]
            
            for email, telefono, comuna, ciudad in contactos:
                cursor.execute("""
                    INSERT INTO informacion_contacto (email, telefono, comuna, ciudad)
                    VALUES (%s, %s, %s, %s)
                """, (email, telefono, comuna, ciudad))
            
            # 2. CARRERAS
            print("🎓 Creando carreras...")
            carreras = [
                ('ING001', 'Ingeniería en Informática', 'Carrera de ingeniería enfocada en desarrollo de software'),
                ('TEC001', 'Técnico en Programación', 'Carrera técnica en desarrollo de aplicaciones'),
                ('ING002', 'Ingeniería en Redes', 'Carrera de ingeniería en infraestructura de redes'),
                ('ADM001', 'Administración de Empresas', 'Carrera en gestión empresarial'),
            ]
            
            for codigo, nombre, descripcion in carreras:
                cursor.execute("""
                    INSERT INTO carrera (codigo, nombre, descripcion)
                    VALUES (%s, %s, %s)
                """, (codigo, nombre, descripcion))
            
            # 3. SECCIONES
            print("📚 Creando secciones...")
            secciones = [
                ('001V', 40), ('002V', 35), ('003V', 30),
                ('001D', 25), ('002D', 30), ('003D', 40),
                ('001N', 20), ('002N', 25),
            ]
            
            for codigo, cupo in secciones:
                cursor.execute("""
                    INSERT INTO seccion (codigo, cupo_maximo)
                    VALUES (%s, %s)
                """, (codigo, cupo))
            
            # 4. PERÍODOS ACADÉMICOS
            print("📅 Creando períodos académicos...")
            periodos = [
                (2024, 1, '2024-03-01', '2024-07-31', 'activo'),
                (2024, 2, '2024-08-01', '2024-12-31', 'planificacion'),
                (2023, 2, '2023-08-01', '2023-12-31', 'inactivo'),
            ]
            
            for año, semestre, fecha_inicio, fecha_fin, estado in periodos:
                cursor.execute("""
                    INSERT INTO periodo_academico (año, semestre, fecha_inicio, fecha_fin, estado)
                    VALUES (%s, %s, %s, %s, %s)
                """, (año, semestre, fecha_inicio, fecha_fin, estado))
            
            # 5. PROFESORES
            print("👨‍🏫 Creando profesores...")
            profesores = [
                ('12345678-9', 'Juan Carlos', 'Pérez', 'González', 'jperez', 1),
                ('98765432-1', 'María Elena', 'Rodríguez', 'Silva', 'mrodriguez', 2),
                ('11111111-1', 'Carlos Alberto', 'Mendoza', 'López', 'cmendoza', None),
            ]
            
            for rut, nombre, apellido_p, apellido_m, usuario, contacto_id in profesores:
                cursor.execute("""
                    INSERT INTO profesor (rut, nombre, apellido_paterno, apellido_materno, usuario, informacion_contacto_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (rut, nombre, apellido_p, apellido_m, usuario, contacto_id))
            
            # 6. AUTENTICACIÓN
            print("🔐 Creando sistema de autenticación...")
            # Contraseña por defecto: "123456"
            password_hash = hashlib.sha256("123456".encode()).hexdigest()
            
            usuarios = [
                ('jperez', password_hash, 'profesor', 1),
                ('mrodriguez', password_hash, 'profesor', 2),
                ('cmendoza', password_hash, 'coordinador', 3),
            ]
            
            for usuario, pwd_hash, tipo, profesor_id in usuarios:
                cursor.execute("""
                    INSERT INTO autenticacion (usuario, password_hash, tipo_usuario, profesor_id)
                    VALUES (%s, %s, %s, %s)
                """, (usuario, pwd_hash, tipo, profesor_id))
            
            # 7. ALUMNOS
            print("👨‍🎓 Creando alumnos...")
            alumnos = [
                ('20123456-7', 'Carlos Andrés', 'González', 'Muñoz', 1, 3),
                ('20234567-8', 'Ana María', 'López', 'Fernández', 1, 4),
                ('20345678-9', 'Pedro José', 'Martínez', 'Sánchez', 2, 5),
                ('20456789-0', 'Sofía Isabel', 'Hernández', 'Torres', 2, 6),
                ('20567890-1', 'Diego Alejandro', 'Vargas', 'Morales', 1, 7),
                ('20678901-2', 'Camila Francisca', 'Rojas', 'Castillo', 1, None),
                ('20789012-3', 'Matías Sebastián', 'Silva', 'Reyes', 2, None),
                ('20890123-4', 'Valentina Andrea', 'Torres', 'Guerrero', 1, None),
            ]
            
            for rut, nombre, apellido_p, apellido_m, carrera_id, contacto_id in alumnos:
                cursor.execute("""
                    INSERT INTO alumno (rut, nombre, apellido_paterno, apellido_materno, carrera_id, informacion_contacto_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (rut, nombre, apellido_p, apellido_m, carrera_id, contacto_id))
            
            # 8. MATRÍCULAS
            print("📝 Creando matrículas...")
            for i in range(1, 9):  # Para todos los alumnos
                cursor.execute("""
                    INSERT INTO matricula (alumno_id, estado)
                    VALUES (%s, 'matriculado')
                """, (i,))
            
            # 9. CLASES
            print("🏫 Creando clases...")
            fecha_base = date.today() - timedelta(days=30)
            clases = [
                ('Programación Web Avanzada', 1, fecha_base, '08:00:00', '09:30:00', 'A301', 'presencial', 1, 1),
                ('Programación Web Avanzada', 2, fecha_base + timedelta(days=2), '10:00:00', '11:30:00', 'A302', 'presencial', 1, 1),
                ('Base de Datos II', 1, fecha_base + timedelta(days=1), '14:00:00', '15:30:00', 'B201', 'presencial', 1, 2),
                ('Desarrollo Móvil', 3, fecha_base + timedelta(days=3), '16:00:00', '17:30:00', 'C101', 'hibrida', 1, 1),
                ('Redes y Comunicaciones', 4, fecha_base + timedelta(days=4), '09:00:00', '10:30:00', 'D401', 'presencial', 1, 2),
                # Clases para la semana siguiente
                ('Programación Web Avanzada', 1, fecha_base + timedelta(days=7), '08:00:00', '09:30:00', 'A301', 'presencial', 1, 1),
                ('Base de Datos II', 1, fecha_base + timedelta(days=8), '14:00:00', '15:30:00', 'B201', 'presencial', 1, 2),
            ]
            
            for nombre, seccion_id, fecha, hora_i, hora_f, sala, modalidad, periodo_id, profesor_id in clases:
                cursor.execute("""
                    INSERT INTO clase (nombre, seccion_id, fecha, hora_inicio, hora_fin, sala, modalidad, periodo_academico_id, profesor_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (nombre, seccion_id, fecha, hora_i, hora_f, sala, modalidad, periodo_id, profesor_id))
            
            # 10. RELACIONES PROFESOR-CLASE
            print("👨‍🏫 Asignando profesores a clases...")
            profesor_clases = [
                (1, 1, 'titular'), (1, 2, 'titular'), (1, 6, 'titular'),
                (2, 3, 'titular'), (2, 7, 'titular'),
                (1, 4, 'titular'), (2, 5, 'titular'),
            ]
            
            for profesor_id, clase_id, rol in profesor_clases:
                cursor.execute("""
                    INSERT INTO profesor_clase (profesor_id, clase_id, rol)
                    VALUES (%s, %s, %s)
                """, (profesor_id, clase_id, rol))
            
            # 11. INSCRIPCIONES ALUMNO-CLASE
            print("📚 Inscribiendo alumnos en clases...")
            # Inscribir alumnos 1-4 en las primeras clases, alumnos 5-8 en otras
            inscripciones = [
                # Clase 1: Programación Web Avanzada
                (1, 1), (2, 1), (5, 1), (6, 1),
                # Clase 2: Programación Web Avanzada  
                (3, 2), (4, 2), (7, 2), (8, 2),
                # Clase 3: Base de Datos II
                (1, 3), (3, 3), (5, 3), (7, 3),
                # Clase 4: Desarrollo Móvil
                (2, 4), (4, 4), (6, 4), (8, 4),
                # Clase 5: Redes y Comunicaciones
                (1, 5), (2, 5), (3, 5), (4, 5),
                # Repetir para clases de la semana siguiente
                (1, 6), (2, 6), (5, 6), (6, 6),
                (1, 7), (3, 7), (5, 7), (7, 7),
            ]
            
            for alumno_id, clase_id in inscripciones:
                cursor.execute("""
                    INSERT INTO alumno_clase (alumno_id, clase_id, estado)
                    VALUES (%s, %s, 'inscrito')
                """, (alumno_id, clase_id))
            
            # 12. REGISTROS DE ASISTENCIA DE PRUEBA
            print("✅ Creando registros de asistencia de prueba...")
            # Crear asistencia para las primeras 3 clases
            asistencias = [
                # Clase 1
                (1, 1, True), (2, 1, True), (5, 1, False), (6, 1, True),
                # Clase 3 
                (1, 3, True), (3, 3, False), (5, 3, True), (7, 3, True),
                # Clase 5
                (1, 5, True), (2, 5, True), (3, 5, True), (4, 5, False),
            ]
            
            for clase_id, alumno_id, presente in asistencias:
                # Usar la fecha de la clase correspondiente
                cursor.execute("SELECT fecha FROM clase WHERE id = %s", (clase_id,))
                fecha_clase = cursor.fetchone()[0]
                
                cursor.execute("""
                    INSERT INTO asistencia (clase_id, alumno_id, presente, fecha_asistencia, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                """, (clase_id, alumno_id, presente, fecha_clase, fecha_clase))
            
            # Confirmar todos los cambios
            conexion.commit()
            
            # 13. DATOS INICIALES PARA NUEVAS FUNCIONALIDADES
            print("🔐 Creando permisos del sistema...")
            permisos_data = [
                # Gestión de usuarios
                ('manage_users', 'Gestionar usuarios del sistema', 'usuarios'),
                ('view_users', 'Ver lista de usuarios', 'usuarios'),
                ('create_users', 'Crear nuevos usuarios', 'usuarios'),
                ('edit_users', 'Editar información de usuarios', 'usuarios'),
                ('delete_users', 'Eliminar usuarios', 'usuarios'),
                
                # Gestión de clases
                ('manage_classes', 'Gestionar clases', 'academico'),
                ('view_classes', 'Ver clases', 'academico'),
                ('create_classes', 'Crear nuevas clases', 'academico'),
                ('edit_classes', 'Editar información de clases', 'academico'),
                ('delete_classes', 'Eliminar clases', 'academico'),
                
                # Asistencia
                ('manage_attendance', 'Gestionar asistencia', 'asistencia'),
                ('view_attendance', 'Ver registros de asistencia', 'asistencia'),
                ('edit_attendance', 'Modificar registros de asistencia', 'asistencia'),
                ('bulk_attendance', 'Registrar asistencia masiva', 'asistencia'),
                
                # Reportes
                ('view_reports', 'Ver reportes', 'reportes'),
                ('create_reports', 'Crear reportes personalizados', 'reportes'),
                ('export_reports', 'Exportar reportes', 'reportes'),
                ('schedule_reports', 'Programar reportes automáticos', 'reportes'),
                
                # Sistema
                ('manage_system', 'Gestionar configuración del sistema', 'sistema'),
                ('view_logs', 'Ver logs del sistema', 'sistema'),
                ('manage_roles', 'Gestionar roles y permisos', 'sistema'),
                ('system_backup', 'Realizar copias de seguridad', 'sistema'),
            ]
            
            for nombre, descripcion, categoria in permisos_data:
                cursor.execute("""
                    INSERT INTO permisos (nombre, descripcion, categoria)
                    VALUES (%s, %s, %s)
                """, (nombre, descripcion, categoria))
            
            print("👥 Creando roles del sistema...")
            roles_data = [
                ('admin', 'Administrador del sistema', 5),
                ('coordinador', 'Coordinador académico', 4),
                ('profesor', 'Profesor', 3),
                ('ayudante', 'Ayudante de cátedra', 2),
                ('invitado', 'Usuario invitado', 1),
            ]
            
            for nombre, descripcion, nivel in roles_data:
                cursor.execute("""
                    INSERT INTO roles (nombre, descripcion, nivel_acceso)
                    VALUES (%s, %s, %s)
                """, (nombre, descripcion, nivel))
            
            print("🔗 Asignando permisos a roles...")
            # Admin: todos los permisos
            cursor.execute("SELECT id FROM permisos")
            todos_permisos = [row[0] for row in cursor.fetchall()]
            
            for permiso_id in todos_permisos:
                cursor.execute("""
                    INSERT INTO rol_permisos (rol_id, permiso_id, granted_by)
                    VALUES (1, %s, 1)
                """, (permiso_id,))
            
            # Coordinador: permisos académicos y de reportes
            permisos_coordinador = [
                'view_users', 'manage_classes', 'view_classes', 'create_classes', 'edit_classes',
                'manage_attendance', 'view_attendance', 'edit_attendance', 'bulk_attendance',
                'view_reports', 'create_reports', 'export_reports', 'schedule_reports',
                'view_logs'
            ]
            
            for permiso_nombre in permisos_coordinador:
                cursor.execute("""
                    INSERT INTO rol_permisos (rol_id, permiso_id, granted_by)
                    SELECT 2, p.id, 1 FROM permisos p WHERE p.nombre = %s
                """, (permiso_nombre,))
            
            # Profesor: permisos básicos
            permisos_profesor = [
                'view_classes', 'manage_attendance', 'view_attendance', 
                'view_reports', 'export_reports'
            ]
            
            for permiso_nombre in permisos_profesor:
                cursor.execute("""
                    INSERT INTO rol_permisos (rol_id, permiso_id, granted_by)
                    SELECT 3, p.id, 1 FROM permisos p WHERE p.nombre = %s
                """, (permiso_nombre,))
            
            # Ayudante: permisos limitados
            permisos_ayudante = ['view_classes', 'view_attendance', 'view_reports']
            
            for permiso_nombre in permisos_ayudante:
                cursor.execute("""
                    INSERT INTO rol_permisos (rol_id, permiso_id, granted_by)
                    SELECT 4, p.id, 1 FROM permisos p WHERE p.nombre = %s
                """, (permiso_nombre,))
            
            print("👤 Asignando roles a usuarios...")
            # Asignar roles a los usuarios existentes
            usuarios_roles = [
                (1, 3),  # jperez -> profesor
                (2, 3),  # mrodriguez -> profesor  
                (3, 2),  # cmendoza -> coordinador
            ]
            
            for usuario_id, rol_id in usuarios_roles:
                cursor.execute("""
                    INSERT INTO usuario_roles (usuario_id, rol_id, assigned_by)
                    VALUES (%s, %s, 1)
                """, (usuario_id, rol_id))
            
            print("⚙️ Creando configuraciones del sistema...")
            configuraciones_data = [
                ('app_name', 'Sistema de Asistencia DuocUC', 'string', 'Nombre de la aplicación', 'general'),
                ('session_timeout', '3600', 'integer', 'Tiempo de expiración de sesión en segundos', 'seguridad'),
                ('max_login_attempts', '5', 'integer', 'Máximo intentos de login fallidos', 'seguridad'),
                ('lockout_duration', '900', 'integer', 'Duración del bloqueo en segundos', 'seguridad'),
                ('password_min_length', '8', 'integer', 'Longitud mínima de contraseña', 'seguridad'),
                ('require_password_complexity', 'true', 'boolean', 'Requerir complejidad en contraseñas', 'seguridad'),
                ('attendance_tolerance_minutes', '15', 'integer', 'Tolerancia en minutos para asistencia', 'academico'),
                ('min_attendance_percentage', '75', 'integer', 'Porcentaje mínimo de asistencia requerido', 'academico'),
                ('notification_email_enabled', 'true', 'boolean', 'Habilitar notificaciones por email', 'notificaciones'),
                ('backup_frequency_days', '7', 'integer', 'Frecuencia de backup automático en días', 'sistema'),
            ]
            
            for clave, valor, tipo, descripcion, categoria in configuraciones_data:
                cursor.execute("""
                    INSERT INTO configuraciones (clave, valor, tipo, descripcion, categoria, updated_by)
                    VALUES (%s, %s, %s, %s, %s, 1)
                """, (clave, valor, tipo, descripcion, categoria))
            
            print("📢 Creando alertas del sistema...")
            alertas_data = [
                ('baja_asistencia', 'Alerta de Baja Asistencia', 
                 'Detectar estudiantes con asistencia menor al 75%',
                 '{"porcentaje_minimo": 75, "verificar_cada": "daily"}'),
                ('sistema', 'Alerta de Rendimiento del Sistema',
                 'Monitorear el rendimiento y disponibilidad del sistema',
                 '{"check_memory": true, "check_disk": true, "verificar_cada": "hourly"}'),
            ]
            
            for tipo, titulo, descripcion, criterios in alertas_data:
                cursor.execute("""
                    INSERT INTO alertas_sistema (tipo, titulo, descripcion, criterios, created_by, proxima_verificacion)
                    VALUES (%s, %s, %s, %s, 1, DATE_ADD(NOW(), INTERVAL 1 HOUR))
                """, (tipo, titulo, descripcion, criterios))
            
            # Confirmar todos los cambios
            conexion.commit()
            
            print("✅ Datos de prueba creados exitosamente!")
            
            # Mostrar resumen
            mostrar_resumen()
            
            return True
            
    except Exception as e:
        print(f"❌ Error creando datos de prueba: {e}")
        return False

def mostrar_resumen():
    """Mostrar resumen de los datos creados"""
    print("\n📊 RESUMEN DE DATOS CREADOS:")
    print("="*50)
    
    try:
        with db.get_connection() as conexion:
            cursor = conexion.cursor()
            
            tablas = [
                ('informacion_contacto', 'Contactos'),
                ('carrera', 'Carreras'),
                ('seccion', 'Secciones'),
                ('periodo_academico', 'Períodos Académicos'),
                ('profesor', 'Profesores'),
                ('autenticacion', 'Usuarios'),
                ('alumno', 'Alumnos'),
                ('matricula', 'Matrículas'),
                ('clase', 'Clases'),
                ('profesor_clase', 'Asignaciones Profesor-Clase'),
                ('alumno_clase', 'Inscripciones'),
                ('asistencia', 'Registros de Asistencia'),
                ('permisos', 'Permisos'),
                ('roles', 'Roles'),
                ('rol_permisos', 'Asignaciones de Permisos a Roles'),
                ('usuario_roles', 'Asignaciones de Roles a Usuarios'),
                ('configuraciones', 'Configuraciones del Sistema'),
                ('alertas_sistema', 'Alertas del Sistema'),
            ]
            
            for tabla, nombre in tablas:
                cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
                count = cursor.fetchone()[0]
                print(f"{nombre:.<25} {count:>3} registros")
    
    except Exception as e:
        print(f"Error mostrando resumen: {e}")

def mostrar_credenciales():
    """Mostrar credenciales de acceso"""
    print("\n🔑 CREDENCIALES DE ACCESO:")
    print("="*50)
    print("Usuario: jperez")
    print("Contraseña: 123456")
    print("Rol: Profesor")
    print()
    print("Usuario: mrodriguez") 
    print("Contraseña: 123456")
    print("Rol: Profesor")
    print()
    print("Usuario: cmendoza")
    print("Contraseña: 123456") 
    print("Rol: Coordinador")
    print()

def limpiar_datos():
    """Limpiar todos los datos de la base de datos"""
    print("🗑️ Limpiando datos existentes...")
    
    try:
        with db.get_connection() as conexion:
            cursor = conexion.cursor()
            
            # Deshabilitar checks de foreign key temporalmente
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # Lista de tablas en orden inverso de dependencias
            tablas = [
                'historial_reportes', 'reportes_programados', 'alertas_sistema',
                'notificaciones', 'sesiones_activas', 'login_attempts', 'logs_auditoria',
                'usuario_roles', 'rol_permisos', 'roles', 'permisos', 'configuraciones',
                'asistencia', 'registro_facial', 'alumno_clase', 'profesor_clase',
                'clase', 'matricula', 'alumno', 'autenticacion', 'profesor',
                'periodo_academico', 'seccion', 'carrera', 'informacion_contacto'
            ]
            
            for tabla in tablas:
                cursor.execute(f"DELETE FROM {tabla}")
                print(f"  ✅ Limpiada tabla: {tabla}")
            
            # Reactivar checks de foreign key
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            conexion.commit()
            print("✅ Datos limpiados exitosamente!")
            
    except Exception as e:
        print(f"❌ Error limpiando datos: {e}")

if __name__ == "__main__":
    print("🏫 Sistema de Asistencia DuocUC - Configuración de Datos de Prueba")
    print("="*70)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--limpiar":
        limpiar_datos()
    else:
        # Limpiar datos existentes antes de crear nuevos
        limpiar_datos()
        
        # Crear datos de prueba
        if crear_datos_prueba():
            mostrar_credenciales()
            print("\n🚀 ¡Sistema listo para usar!")
            print("Ejecuta: python run.py")
        else:
            print("\n❌ Error configurando los datos de prueba")
            sys.exit(1)