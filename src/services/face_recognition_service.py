"""
Face Recognition Service for Real-Time User Identification
Handles face detection, encoding, and identification using face_recognition library
"""
import os
import logging
import face_recognition
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from PIL import Image
import io
import base64

logger = logging.getLogger(__name__)


class FaceRecognitionService:
    """
    Service for identifying users based on facial recognition.
    Loads reference images from profiles_pic directory and compares against captured images.
    """

    def __init__(self, profiles_dir: str = "profiles_pic"):
        """
        Initialize the face recognition service
        
        Args:
            profiles_dir: Directory containing profile pictures (default: profiles_pic)
        """
        self.profiles_dir = Path(profiles_dir)
        self.known_face_encodings: List[np.ndarray] = []
        self.known_face_names: List[str] = []
        self.last_identified_user: Optional[str] = None

        # Face recognition settings
        self.tolerance = 0.6  # Lower is more strict (0.6 is default)
        self.model = "hog"  # "hog" is faster, "cnn" is more accurate but requires GPU

        # Load known faces from profiles directory
        self._load_known_faces()

    def _load_known_faces(self):
        """
        Load and encode all face images from the profiles_pic directory.
        Filename (without extension) is used as the person's name.
        """
        if not self.profiles_dir.exists():
            logger.warning(f"Profiles directory '{self.profiles_dir}' does not exist. Creating it.")
            self.profiles_dir.mkdir(parents=True, exist_ok=True)
            return

        supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
        loaded_count = 0

        for image_path in self.profiles_dir.iterdir():
            if image_path.suffix.lower() not in supported_extensions:
                continue

            try:
                # Load image
                image = face_recognition.load_image_file(str(image_path))

                # Get face encodings
                face_encodings = face_recognition.face_encodings(image, model=self.model)

                if len(face_encodings) == 0:
                    logger.warning(f"No face detected in {image_path.name}")
                    continue

                if len(face_encodings) > 1:
                    logger.warning(f"Multiple faces detected in {image_path.name}, using the first one")

                # Store encoding and name (filename without extension)
                self.known_face_encodings.append(face_encodings[0])
                person_name = image_path.stem  # Filename without extension
                self.known_face_names.append(person_name)
                loaded_count += 1

                logger.info(f"Loaded face encoding for: {person_name}")

            except Exception as e:
                logger.error(f"Error loading {image_path.name}: {e}")

        logger.info(f"Loaded {loaded_count} face encodings from {self.profiles_dir}")

    def identify_face_from_base64(self, base64_image: str) -> Optional[Dict[str, any]]:
        """
        Identify a person from a base64-encoded image
        
        Args:
            base64_image: Base64-encoded image string (with or without data URI prefix)
        
        Returns:
            Dict with identification result:
            {
                "name": "person_name" or None,
                "confidence": float (0-1),
                "is_new_user": bool,
                "greeting_message": str or None
            }
        """
        try:
            # Remove data URI prefix if present
            if ',' in base64_image:
                base64_image = base64_image.split(',')[1]

            # Decode base64 to bytes
            image_bytes = base64.b64decode(base64_image)

            # Convert to PIL Image then to numpy array
            pil_image = Image.open(io.BytesIO(image_bytes))
            image_array = np.array(pil_image)

            return self.identify_face_from_array(image_array)

        except Exception as e:
            logger.error(f"Error identifying face from base64: {e}")
            return None

    def identify_face_from_array(self, image_array: np.ndarray) -> Optional[Dict[str, any]]:
        """
        Identify a person from a numpy array image
        
        Args:
            image_array: Numpy array representing an image (RGB format)
        
        Returns:
            Dict with identification result or None if no face detected
        """
        if len(self.known_face_encodings) == 0:
            logger.warning("No known faces loaded. Cannot identify anyone.")
            return {
                "name": None,
                "confidence": 0.0,
                "is_new_user": False,
                "greeting_message": None,
                "error": "No profile pictures loaded. Please add photos to profiles_pic directory."
            }

        try:
            # Detect faces in the captured image
            face_locations = face_recognition.face_locations(image_array, model=self.model)

            if len(face_locations) == 0:
                logger.info("No face detected in the image")
                return {
                    "name": None,
                    "confidence": 0.0,
                    "is_new_user": False,
                    "greeting_message": None,
                    "error": "No face detected in the image"
                }

            if len(face_locations) > 1:
                logger.warning(f"Multiple faces detected ({len(face_locations)}), using the first one")

            # Get face encodings for detected faces
            face_encodings = face_recognition.face_encodings(
                image_array, 
                known_face_locations=face_locations,
                model=self.model
            )

            if len(face_encodings) == 0:
                return {
                    "name": None,
                    "confidence": 0.0,
                    "is_new_user": False,
                    "greeting_message": None,
                    "error": "Could not encode detected face"
                }

            # Use the first detected face
            captured_encoding = face_encodings[0]

            # Compare against known faces
            face_distances = face_recognition.face_distance(
                self.known_face_encodings, 
                captured_encoding
            )

            # Find the best match
            best_match_index = np.argmin(face_distances)
            best_distance = face_distances[best_match_index]

            # Check if the match is within tolerance
            if best_distance <= self.tolerance:
                identified_name = self.known_face_names[best_match_index]
                confidence = 1.0 - best_distance  # Convert distance to confidence score

                # Check if this is a new user (different from last identified)
                is_new_user = (self.last_identified_user != identified_name)

                # Generate greeting message only for new users
                greeting_message = None
                if is_new_user:
                    greeting_message = f"Hello, {identified_name}! Nice to see you."
                    self.last_identified_user = identified_name
                    logger.info(f"New user identified: {identified_name} (confidence: {confidence:.2f})")
                else:
                    logger.info(f"Same user detected: {identified_name} (confidence: {confidence:.2f})")

                return {
                    "name": identified_name,
                    "confidence": float(confidence),
                    "is_new_user": is_new_user,
                    "greeting_message": greeting_message
                }
            else:
                # No match found within tolerance
                logger.info(f"No match found (best distance: {best_distance:.2f})")
                return {
                    "name": None,
                    "confidence": 0.0,
                    "is_new_user": False,
                    "greeting_message": None,
                    "error": "Face detected but not recognized. Please add your photo to profiles_pic."
                }

        except Exception as e:
            logger.error(f"Error during face identification: {e}")
            return {
                "name": None,
                "confidence": 0.0,
                "is_new_user": False,
                "greeting_message": None,
                "error": f"Error during identification: {str(e)}"
            }

    def reset_current_user(self):
        """Reset the currently identified user (useful for testing or manual reset)"""
        self.last_identified_user = None
        logger.info("Current user reset")

    def reload_profiles(self):
        """Reload profile pictures from the profiles_pic directory"""
        self.known_face_encodings = []
        self.known_face_names = []
        self.last_identified_user = None
        self._load_known_faces()
        logger.info("Profile pictures reloaded")

    def get_loaded_profiles(self) -> List[str]:
        """Get list of loaded profile names"""
        return self.known_face_names.copy()

    def get_status(self) -> Dict[str, any]:
        """Get current status of the face recognition service"""
        return {
            "profiles_loaded": len(self.known_face_names),
            "profile_names": self.known_face_names,
            "current_user": self.last_identified_user,
            "profiles_directory": str(self.profiles_dir),
            "tolerance": self.tolerance,
            "model": self.model
        }


# Global instance
_face_recognition_service: Optional[FaceRecognitionService] = None


def get_face_recognition_service() -> FaceRecognitionService:
    """Get or create the global face recognition service instance"""
    global _face_recognition_service
    if _face_recognition_service is None:
        _face_recognition_service = FaceRecognitionService()
    return _face_recognition_service