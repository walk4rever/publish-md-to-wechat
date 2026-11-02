import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import sensitive_scan


class TestSensitiveScan(unittest.TestCase):
    def test_guoban_false_positive_us_office(self):
        required, _, _ = sensitive_scan.scan("我们美国办公室现在的文化很好。")
        self.assertEqual([h["word"] for h in required], [])

    def test_guoban_true_positive(self):
        required, _, _ = sensitive_scan.scan("文件由国办印发。")
        self.assertIn("国办", [h["word"] for h in required])

    def test_guoban_mixed_counts(self):
        required, _, _ = sensitive_scan.scan("美国办公室转发了国办的文件。")
        hits = {h["word"]: h["count"] for h in required}
        self.assertEqual(hits.get("国办"), 1)


if __name__ == "__main__":
    unittest.main()
