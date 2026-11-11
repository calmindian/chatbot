import unittest

from app.settings import GIF_HEIGHT, GIF_WIDTH, IMAGE_HEIGHT, IMAGE_WIDTH


class ImageDimensionTests(unittest.TestCase):
    def test_still_images_use_3_by_4_dimensions(self):
        self.assertEqual(IMAGE_WIDTH * 4, IMAGE_HEIGHT * 3)
        self.assertEqual(IMAGE_WIDTH % 8, 0)
        self.assertEqual(IMAGE_HEIGHT % 8, 0)

    def test_gifs_use_3_by_4_dimensions(self):
        self.assertEqual(GIF_WIDTH * 4, GIF_HEIGHT * 3)
        self.assertEqual(GIF_WIDTH % 8, 0)
        self.assertEqual(GIF_HEIGHT % 8, 0)


if __name__ == "__main__":
    unittest.main()
