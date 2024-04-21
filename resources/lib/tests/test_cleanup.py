#!/usr/bin/python

import sys
import textwrap
import unittest
from pathlib import Path

if __name__ == '__main__' and not __package__:
    __package__ = 'resources.lib.tests'
    sys.path.append(str(Path(__file__).resolve().parents[len(__package__.split("."))]))
    try:
        sys.path.remove(str(Path(__file__).resolve().parent))
    except ValueError:
        pass

from ..providers.cleanupdecoratorprovider import CleanupDecoratorProvider


class TestTextCleanup(unittest.TestCase):

    def __test_custom_cleanup(self, source_text: str, expected_text: str) -> None:
        source_text = textwrap.dedent(source_text)
        expected_text = textwrap.dedent(expected_text).strip()
        cleanup_text = CleanupDecoratorProvider.apply_custom_rules(source_text)
        self.assertEqual(cleanup_text, expected_text)

    text2 = """
    <FONT color="#ffff00">- There's news,</FONT> <FONT color="#ffff00">I have to tell you something.</FONT><FONT color="#ffffff">
    - What?</FONT color="#ffff00"> FONT>
    """

    def test_custom_cleanup_with_start_font_tag(self) -> None:
        source_text = """
        <FONT color="#111111">some text</font>
        FONT COLOR='#222222'>some text</font>
        <FONT COLOR='#333333'>some text</font>
        </FONT color="#444444">some text</font>
        """
        expected_text = """
        <font color="#111111">some text</font>
        <font color="#222222">some text</font>
        <font color="#333333">some text</font>
        <font color="#444444">some text</font>
        """
        self.__test_custom_cleanup(source_text, expected_text)

    def test_custom_cleanup_with_end_font_tag(self) -> None:
        source_text = """
        <font color="#111111">some text</FONT>
        <font color="#222222">some text<FONT>
        <font color="#333333">some textFONT>
        """
        expected_text = """
        <font color="#111111">some text</font>
        <font color="#222222">some text</font>
        <font color="#333333">some text</font>
        """
        self.__test_custom_cleanup(source_text, expected_text)

    def test_custom_cleanup_with_redundant_multiple_font_tag(self) -> None:
        source_text = """
        <font color="#111111">some text</font>
        <font color="#111111">some text</font>
        <font color="#111111">some text</font>
        """
        expected_text = """
        <font color="#111111">some text
        some text
        some text</font>
        """
        self.__test_custom_cleanup(source_text, expected_text)

    def test_custom_cleanup_with_redundant_empty_font_tag(self) -> None:
        source_text = """
        <font color="#ffff00">some text.
        some </font><font color="#ffff00">more text.</font>
        """
        expected_text = """
        <font color="#ffff00">some text.
        some more text.</font>
        """
        self.__test_custom_cleanup(source_text, expected_text)

    def test_custom_cleanup_with_redundant_spaces_font_tag(self) -> None:
        source_text = """
        <font color="#ffff00">some text.
        some </font>  <font color="#ffff00">more text.</font>
        """
        expected_text = """
        <font color="#ffff00">some text.
        some more text.</font>
        """
        self.__test_custom_cleanup(source_text, expected_text)

    def test_custom_cleanup_with_redundant_chars_font_tag(self) -> None:
        source_text = """
        <font color="#ffff00">some text.
        some </font> XX <font color="#ffff00">more text.</font>
        """
        expected_text = """
        <font color="#ffff00">some text.
        some XX more text.</font>
        """
        self.__test_custom_cleanup(source_text, expected_text)

    def test_custom_cleanup_with_begining_spaces(self) -> None:
        source_text = """
          <font color="#ffff00">some text
        <font color="#ffff00">  some text
        """
        expected_text = """
        <font color="#ffff00">some text
        <font color="#ffff00">some text
        """
        self.__test_custom_cleanup(source_text, expected_text)

    def test_custom_cleanup_with_end_spaces(self) -> None:
        source_text = f"""
        - some text.  </font>
        - some text.</font>{'  '}
        """
        expected_text = """
        - some text.</font>
        - some text.</font>
        """
        self.__test_custom_cleanup(source_text, expected_text)


if __name__ == '__main__':
    unittest.main()
