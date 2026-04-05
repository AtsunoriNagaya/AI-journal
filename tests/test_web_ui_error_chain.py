import unittest

from web_ui import _format_error_chain


class FormatErrorChainTests(unittest.TestCase):
    def test_follows_cause_chain(self) -> None:
        try:
            try:
                raise ValueError("inner")
            except ValueError as err:
                raise RuntimeError("outer") from err
        except RuntimeError as error:
            chain = _format_error_chain(error)

        self.assertEqual(chain, "RuntimeError: outer <- ValueError: inner")

    def test_stops_when_context_is_suppressed(self) -> None:
        try:
            try:
                raise ValueError("inner")
            except ValueError:
                raise RuntimeError("outer") from None
        except RuntimeError as error:
            chain = _format_error_chain(error)

        self.assertEqual(chain, "RuntimeError: outer")


if __name__ == "__main__":
    unittest.main()
