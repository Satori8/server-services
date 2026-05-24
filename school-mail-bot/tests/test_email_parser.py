import unittest
from email_parser import EmailParser


class TestEmailParser(unittest.TestCase):
    def test_clean_html(self) -> None:
        html_content = """
        <html>
            <head><style>body { color: red; }</style></head>
            <body>
                <h1>Hello Parents!</h1>
                <p>There will be no school on Monday <a href="http://school.com">link</a>.</p>
                <script>alert("test");</script>
            </body>
        </html>
        """
        cleaned = EmailParser.html_to_text(html_content)
        self.assertIn("Hello Parents!", cleaned)
        self.assertIn("There will be no school on Monday link.", cleaned)
        self.assertNotIn("body { color", cleaned)
        self.assertNotIn('alert("test")', cleaned)


if __name__ == "__main__":
    unittest.main()
