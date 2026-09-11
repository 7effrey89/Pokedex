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
        from src.config import get_storage_paths
        self.profiles_dir = get_storage_paths().profile_images
        self.known_face_records: List[Dict[str, Any]] = []
        self.known_face_encodings: List[np.ndarray] = []
        self.known_face_names: List[str] = []
        self.last_identified_user: Optional[str] = None

        # Face recognition settings
        self.tolerance = 0.6  # Lower is more strict (0.6 is default)
        self.model = "hog"  # "hog" is faster, "cnn" is more accurate but requires GPU

        # Load known faces from database and profiles directory
        self._load_known_faces()

    def _load_known_faces(self):
        """
        Load known faces from SQLite user account members and standalone profiles directory.
        """
        self.known_face_records = []
        self.known_face_encodings = []
        self.known_face_names = []

        # 1. Load from User Account Database
        try:
            from src.services.user_account_service import get_user_account_service
            account_service = get_user_account_service()
            db_records = account_service.get_known_face_encodings()
            for rec in db_records:
                self.known_face_records.append(rec)
                self.known_face_encodings.append(rec["encoding"])
                self.known_face_names.append(rec["name"])
            logger.info("Loaded %d face encodings from SQLite account members", len(db_records))
        except Exception as exc:
            logger.warning("Could not load face encodings from account members: %s", exc)

        # 2. Legacy filesystem fallback from profiles directory
        if self.profiles_dir.exists():
            supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
            existing_names = set(self.known_face_names)

            for image_path in self.profiles_dir.iterdir():
                if image_path.suffix.lower() not in supported_extensions:
                    continue
                person_name = image_path.stem
                if person_name.startswith("user-") or person_name in existing_names:
                    continue

                try:
                    image = face_recognition.load_image_file(str(image_path))
                    face_encodings = face_recognition.face_encodings(image, model=self.model)
                    if len(face_encodings) > 0:
                        self.known_face_records.append({
                            "member_id": None,
                            "user_id": None,
                            "name": person_name,
                            "avatar_path": str(image_path),
                            "encoding": face_encodings[0],
                        })
                        self.known_face_encodings.append(face_encodings[0])
                        self.known_face_names.append(person_name)
                        existing_names.add(person_name)
                except Exception as e:
                    logger.error(f"Error loading legacy profile {image_path.name}: {e}")

        logger.info(f"Total {len(self.known_face_encodings)} face encodings active in service")

    def identify_face_from_base64(self, base64_image: str, user_id: Optional[int] = None) -> Optional[Dict[str, any]]:
        """
        Identify a person from a base64-encoded image
        
        Args:
            base64_image: Base64-encoded image string (with or without data URI prefix)
            user_id: Optional user account ID to scope member identification to
        
        Returns:
            Dict with identification result
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

            return self.identify_face_from_array(image_array, user_id=user_id)

        except Exception as e:
            logger.error(f"Error identifying face from base64: {e}")
            return None

    def identify_face_from_array(self, image_array: np.ndarray, user_id: Optional[int] = None) -> Optional[Dict[str, any]]:
        """
        Identify a person from a numpy array image, optionally scoped to an account's members.
        """
        # Determine which encodings to compare against (scoped vs all)
        target_records = self.known_face_records
        if user_id is not None:
            user_records = [r for r in self.known_face_records if r.get("user_id") == user_id]
            if user_records:
                target_records = user_records

        if len(target_records) == 0:
            logger.warning("No face profiles loaded for matching.")
            return {
                "name": None,
                "confidence": 0.0,
                "is_new_user": False,
                "greeting_message": None,
                "error": "No member face profiles loaded. Add member photos in your Account menu."
            }

        target_encodings = [r["encoding"] for r in target_records]
        target_names = [r["name"] for r in target_records]

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
                target_encodings, 
                captured_encoding
            )

            # Find the best match
            best_match_index = np.argmin(face_distances)
            best_distance = face_distances[best_match_index]

            # Check if the match is within tolerance
            if best_distance <= self.tolerance:
                matched_record = target_records[best_match_index]
                identified_name = target_names[best_match_index]
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
                    "member_id": matched_record.get("member_id"),
                    "user_id": matched_record.get("user_id"),
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
                    "error": "Face detected but not recognized in your account members."
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