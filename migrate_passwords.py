#!/usr/bin/env python3
"""
Script para migrar contraseñas de SHA256 a bcrypt
Sistema de Asistencia DuocUC
"""

import sys
import os

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.auth import PasswordMigrator
from app.database import db

def main():
    print("🔐 Sistema de Migración de Contraseñas")
    print("="*50)
    print("Este script migrará todas las contraseñas de SHA256 a bcrypt")
    
    # Verificar conexión
    if not db.test_connection():
        print("❌ No se puede conectar a MySQL")
        return False
    
    # Migrar contraseñas
    print("\n🚀 Iniciando migración...")
    if PasswordMigrator.migrate_all_passwords():
        print("✅ Migración completada exitosamente!")
        print("\n📝 Notas importantes:")
        print("- Todas las contraseñas han sido migradas a bcrypt")
        print("- Las contraseñas existentes siguen funcionando")
        print("- El sistema es más seguro ahora")
        print("- Los usuarios pueden cambiar sus contraseñas desde el sistema")
    else:
        print("❌ Error durante la migración")
        return False

if __name__ == "__main__":
    main() 