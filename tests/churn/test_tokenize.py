import unittest
from scripts.churn import tokenize


class TestTokenize(unittest.TestCase):
    def test_deterministic_same_input_same_token(self):
        a = tokenize.tokenize("C-100", "secret-key")
        b = tokenize.tokenize("C-100", "secret-key")
        self.assertEqual(a, b)

    def test_different_customer_id_different_token(self):
        a = tokenize.tokenize("C-100", "secret-key")
        b = tokenize.tokenize("C-101", "secret-key")
        self.assertNotEqual(a, b)

    def test_different_secret_different_token(self):
        a = tokenize.tokenize("C-100", "secret-A")
        b = tokenize.tokenize("C-100", "secret-B")
        self.assertNotEqual(a, b)

    def test_token_does_not_contain_the_raw_id(self):
        tok = tokenize.tokenize("田中一郎", "secret-key")
        self.assertNotIn("田中", tok)
        self.assertTrue(tok.startswith("t_"))

    def test_empty_secret_is_rejected(self):
        # 弱い/空の鍵で黙ってトークン化しない(仮名化が無意味になるため)
        with self.assertRaises(ValueError):
            tokenize.tokenize("C-100", "")

    def test_empty_customer_id_is_rejected(self):
        with self.assertRaises(ValueError):
            tokenize.tokenize("", "secret-key")


if __name__ == "__main__":
    unittest.main()
