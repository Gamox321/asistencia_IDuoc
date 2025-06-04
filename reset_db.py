#!/usr/bin/env python3
"""
Script para resetear completamente la base de datos MySQL
Sistema de Asistencia DuocUC
"""

import sys
import os

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import db

def resetear_base_datos():
    """Resetear completamente la base de datos"""
    print("🗑️ Reseteando base de datos completa...")
    
    if db.reset_database():
        print("✅ Base de datos reseteada exitosamente!")
        return True
    else:
        print("❌ Error reseteando la base de datos")
        return False

if __name__ == "__main__":
    print("🏫 Sistema de Asistencia DuocUC - Reset de Base de Datos")
    print("="*60)
    
    if resetear_base_datos():
        print("\n🚀 Base de datos lista para usar")
        print("Ejecuta: python test_db.py")
    else:
        print("\n❌ Error reseteando la base de datos")
        sys.exit(1) 