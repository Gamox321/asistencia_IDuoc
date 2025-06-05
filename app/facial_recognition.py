# Importación opcional de face_recognition
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    print("⚠️ face_recognition no está disponible en facial_recognition.py")

import numpy as np
import cv2
from typing import Tuple, List, Optional
import base64
import re

class FacialRecognition:
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_names = []
        
    def add_face(self, image_data: str, student_id: str) -> bool:
        """
        Añade una cara a la base de datos de caras conocidas
        image_data: string base64 de la imagen
        student_id: identificador del estudiante
        """
        if not FACE_RECOGNITION_AVAILABLE:
            return False
        try:
            # Convertir base64 a imagen
            image_data = re.sub('^data:image/.+;base64,', '', image_data)
            image_bytes = base64.b64decode(image_data)
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            # Convertir BGR a RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Detectar caras en la imagen
            face_locations = face_recognition.face_locations(rgb_image)
            if not face_locations:
                return False
            
            # Obtener encoding de la cara
            face_encoding = face_recognition.face_encodings(rgb_image, face_locations)[0]
            
            # Guardar encoding y nombre
            self.known_face_encodings.append(face_encoding)
            self.known_face_names.append(student_id)
            
            return True
        except Exception as e:
            print(f"Error al añadir cara: {str(e)}")
            return False
    
    def recognize_face(self, image_data: str) -> Optional[str]:
        """
        Reconoce una cara en la imagen proporcionada
        image_data: string base64 de la imagen
        Retorna: ID del estudiante si se encuentra una coincidencia, None en caso contrario
        """
        if not FACE_RECOGNITION_AVAILABLE:
            return None
        try:
            # Convertir base64 a imagen
            image_data = re.sub('^data:image/.+;base64,', '', image_data)
            image_bytes = base64.b64decode(image_data)
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            # Convertir BGR a RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Detectar caras en la imagen
            face_locations = face_recognition.face_locations(rgb_image)
            if not face_locations:
                return None
            
            # Obtener encoding de la cara
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            
            for face_encoding in face_encodings:
                # Comparar con caras conocidas
                matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=0.6)
                
                if True in matches:
                    # Encontrar la cara más similar
                    face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                    best_match_index = np.argmin(face_distances)
                    
                    if matches[best_match_index]:
                        return self.known_face_names[best_match_index]
            
            return None
        except Exception as e:
            print(f"Error al reconocer cara: {str(e)}")
            return None

# Instancia global del reconocimiento facial
facial_recognition = FacialRecognition() 