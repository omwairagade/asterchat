import unittest

from aster.llm import render_markdown


class MarkdownSafetyTests(unittest.TestCase):
    def test_untrusted_html_and_javascript_links_are_not_rendered(self):
        rendered = render_markdown('Hello <script>alert(1)</script> [unsafe](javascript:alert(1))')
        self.assertNotIn("<script>", rendered.lower())
        self.assertNotIn("javascript:", rendered.lower())
        self.assertIn("Hello", rendered)


if __name__ == "__main__":
    unittest.main()
