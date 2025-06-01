import sqlite3
import os
from datetime import datetime
from .config import Config

def eliminar_asistencias():
    try:
        # Usar la ruta de la base de datos desde la configuración
        db_path = Config.DATABASE_PATH
        if not os.path.exists(db_path):
            print(f"Error: No se encontró la base de datos en {db_path}")
            return False

        # Pedir confirmación al usuario
        print("\n¡ADVERTENCIA!")
        print("=" * 50)
        print("Está a punto de eliminar TODOS los registros de asistencia.")
        print("Esta acción no se puede deshacer.")
        print("=" * 50)
        
        confirmacion = input("\n¿Está seguro que desea continuar? (escriba 'SI' para confirmar): ")
        
        if confirmacion.upper() != 'SI':
            print("\nOperación cancelada.")
            return False

        # Conectar a la base de datos y crear un backup antes de eliminar
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Crear backup en el directorio data
        backup_filename = f"backup_asistencia_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(Config.DATA_DIR, backup_filename)
        backup_conn = sqlite3.connect(backup_path)
        conn.backup(backup_conn)
        backup_conn.close()
        print(f"\nBackup creado: {backup_path}")

        # Obtener el número de registros antes de eliminar
        cursor.execute("SELECT COUNT(*) FROM asistencia")
        num_registros = cursor.fetchone()[0]

        # Eliminar los registros
        cursor.execute("DELETE FROM asistencia")
        conn.commit()

        print(f"\nSe han eliminado {num_registros} registros de asistencia.")
        print("La operación se completó exitosamente.")

        # Cerrar la conexión
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"\nError en la base de datos: {str(e)}")
        return False
    except Exception as e:
        print(f"\nError inesperado: {str(e)}")
        return False

def main():
    print("\nEliminación de Registros de Asistencia")
    print("=" * 40)
    # Inicializar la configuración antes de ejecutar
    Config.init_app()
    eliminar_asistencias()

if __name__ == "__main__":
    main() 