import unittest

from src.viewer.markdown_renderer import render_markdown_html


class MarkdownRendererTests(unittest.TestCase):
    def test_target_attribute_is_removed(self) -> None:
        markdown_text = '<a href="https://example.com" target="_blank">link</a>'

        html = render_markdown_html(markdown_text)

        self.assertIn('href="https://example.com"', html)
        self.assertNotIn('target="_blank"', html)

    def test_rel_contains_safe_tokens(self) -> None:
        markdown_text = "[example](https://example.com)"

        html = render_markdown_html(markdown_text)

        self.assertIn('rel="nofollow noopener noreferrer"', html)

    def test_markdown_link_never_has_target_attribute(self) -> None:
        markdown_text = "[safe link](https://example.com)"

        html = render_markdown_html(markdown_text)

        self.assertIn('href="https://example.com"', html)
        self.assertNotIn('target="_blank"', html)


if __name__ == "__main__":
    unittest.main()
