import unittest
import time
from unittest.mock import patch, mock_open
from key_manager import GeminiKeyManager


class TestGeminiKeyManager(unittest.TestCase):
    @patch(
        "builtins.open", new_callable=mock_open, read_data="key1\n# comment\n\nkey2\n"
    )
    def test_load_keys(self, mock_file) -> None:
        km = GeminiKeyManager("keys.txt")
        self.assertEqual(km.keys, ["key1", "key2"])

    @patch("builtins.open", new_callable=mock_open, read_data="key1\nkey2\n")
    def test_rotation_and_cooldown(self, mock_file) -> None:
        km = GeminiKeyManager("keys.txt")

        # Get first key
        key = km.get_key()
        self.assertEqual(key, "key1")

        # Mark first key on cooldown
        km.mark_cooldown("key1", cooldown_seconds=10)

        # Next key should be key2
        key = km.get_key()
        self.assertEqual(key, "key2")

        # Mark second key on cooldown
        km.mark_cooldown("key2", cooldown_seconds=10)

        # No key available now
        with self.assertRaises(RuntimeError):
            km.get_key()


if __name__ == "__main__":
    unittest.main()
