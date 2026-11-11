import unittest

from app.prompting import image_prompt_from_chat, is_image_request


class ChatImagePromptTests(unittest.TestCase):
    def test_extracts_outfit_from_chat_request(self):
        self.assertEqual(
            image_prompt_from_chat("Change to a long red gown and send me a pic"),
            "a long red gown",
        )

    def test_handles_example_typing_errors(self):
        self.assertEqual(
            image_prompt_from_chat("Chage to gown adn send me a pic"),
            "gown",
        )

    def test_keeps_scene_details_and_removes_image_request(self):
        self.assertEqual(
            image_prompt_from_chat("Show me a photo in a snowy park"),
            "in a snowy park",
        )

    def test_detects_picture_request(self):
        self.assertTrue(is_image_request("Send me a pic in a red gown"))
        self.assertFalse(is_image_request("Tell me about a red gown"))


if __name__ == "__main__":
    unittest.main()
