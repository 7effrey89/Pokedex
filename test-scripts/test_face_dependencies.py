"""Verify that installed face-model resources and the native detector work."""

import unittest
from pathlib import Path


class FaceDependencyTests(unittest.TestCase):
    def test_native_face_detection_handles_blank_image(self):
        import face_recognition_models
        import face_recognition
        import numpy as np

        self.assertTrue(Path(face_recognition_models.face_recognition_model_location()).is_file())
        image = np.zeros((128, 128, 3), dtype=np.uint8)
        self.assertEqual(face_recognition.face_locations(image), [])


if __name__ == "__main__":
    unittest.main()
