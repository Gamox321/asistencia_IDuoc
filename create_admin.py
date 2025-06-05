import mysql.connector
import hashlib
from mysql.connector import Error
from app.config import Config
import random

def generate_unique_rut(cursor):
    """Generar un RUT único que no exista en la base de datos"""
    while True:
        # Generar un número aleatorio entre 1 y 99999999
        num = random.randint(1, 99999999)
        rut = f"{num:08d}"
        
        # Calcular dígito verificador
        reversed_digits = map(int, reversed(str(num)))
        factors = (2, 3, 4, 5, 6, 7)
        s = sum(d * f for d, f in zip(reversed_digits, (factors * 2)[:8]))
        check_digit = (-s) % 11
        if check_digit == 10:
            check_digit = 'K'
        
        rut = f"{rut}-{check_digit}"
        
        # Verificar si el RUT ya existe
        cursor.execute("SELECT id FROM profesor WHERE rut = %s", (rut,))
        if not cursor.fetchone():
            return rut

def create_admin_user():
    try:
        # Establecer conexión usando la configuración de la aplicación
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE
        )
        
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            
            # Verificar si el usuario admin ya existe
            cursor.execute("SELECT id FROM profesor WHERE usuario = 'admin'")
            if cursor.fetchone():
                print("⚠️ El usuario admin ya existe")
                print("Usuario: admin")
                print("Contraseña: 123456")
                return
            
            # Generar RUT único
            rut = generate_unique_rut(cursor)
            
            # 1. Crear el profesor
            cursor.execute("""
                INSERT INTO profesor (rut, nombre, apellido_paterno, apellido_materno, usuario, estado)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (rut, 'Admin', 'Sistema', 'DuocUC', 'admin', 'activo'))
            
            profesor_id = cursor.lastrowid
            
            # 2. Crear credenciales (password: 123456)
            password = '123456'
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            cursor.execute("""
                INSERT INTO autenticacion (usuario, password_hash, tipo_usuario, profesor_id)
                VALUES (%s, %s, %s, %s)
            """, ('admin', password_hash, 'admin', profesor_id))
            
            # 3. Asignar rol de admin (rol_id = 1 para admin)
            cursor.execute("""
                INSERT INTO usuario_roles (usuario_id, rol_id, assigned_by)
                VALUES (%s, 1, %s)
            """, (profesor_id, profesor_id))
            
            # Confirmar cambios
            connection.commit()
            print("✅ Usuario administrador creado exitosamente")
            print("Usuario: admin")
            print("Contraseña: 123456")
            print("\n⚠️ Por seguridad, cambia la contraseña después del primer inicio de sesión")
            
    except Error as e:
        print(f"❌ Error: {e}")
    
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    create_admin_user() 