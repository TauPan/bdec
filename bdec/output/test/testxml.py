#!/usr/bin/env python
import unittest

import bdec.choice as chc
import bdec.data as dt
import bdec.field as fld
import bdec.output.xmlout as xml
import bdec.sequence as seq
import bdec.sequenceof as sof

class TestXml(unittest.TestCase):
    def test_field(self):
        field = fld.Field("bob", 8)
        text = xml.to_string(field, dt.Data.from_hex('8e'))
        self.assertEqual("<bob>\n    10001110\n</bob>\n", text)

    def test_hidden_entry(self):
        sequence = seq.Sequence("bob", [
            fld.Field("cat:", 8, fld.Field.INTEGER),
            fld.Field("dog", 24, fld.Field.TEXT)])
        text = xml.to_string(sequence, dt.Data.from_hex('6e7a6970'))
        self.assertEqual("<bob>\n    <dog>\n        zip\n    </dog>\n</bob>\n", text)

    def test_xml_encode(self):
        text = "<blah><cat>5</cat><dog>18</dog></blah>"
        sequence = seq.Sequence("blah", [
            fld.Field("cat", 8, fld.Field.INTEGER),
            fld.Field("dog", 8, fld.Field.INTEGER)])
        data = reduce(lambda a,b:a+b, xml.encode(sequence, text))
        self.assertEqual("\x05\x12", data.bytes())

    def test_encoded_text_length_ignores_whitespace(self):
        """
        Test that the encode text ignores the additional whitespace that xml puts around the body text.
        """
        text = "<blah><cat>\n    rabbit\n</cat></blah>"
        sequence = seq.Sequence("blah", [fld.Field("cat", 48, fld.Field.TEXT)])
        data = reduce(lambda a,b:a+b, xml.encode(sequence, text))
        self.assertEqual("rabbit", data.bytes())

    def test_choice_encode(self):
        a = fld.Field('a', 8, expected=dt.Data('a'))
        b = fld.Field('b', 8, expected=dt.Data('b'))
        choice = chc.Choice('blah', [a, b])
        text = "<blah><b /></blah>"
        data = reduce(lambda a,b:a+b, xml.encode(choice, text))
        self.assertEqual("b", data.bytes())

    def test_verbose(self):
        sequence = seq.Sequence("bob", [
            fld.Field("cat:", 8, fld.Field.INTEGER),
            fld.Field("dog", 24, fld.Field.TEXT)])
        text = xml.to_string(sequence, dt.Data.from_hex('6d7a6970'), verbose=True)
        expected = """<bob>
    <cat_>
        109
        <!-- hex (1 bytes): 6d -->
    </cat_>
    <dog>
        zip
        <!-- hex (3 bytes): 7a6970 -->
    </dog>
</bob>
"""
        self.assertEqual(expected, text)

        # Now test that we can re-encode verbose generated xml...
        data = reduce(lambda a,b:a+b, xml.encode(sequence, text))
        self.assertEqual("mzip", data.bytes())

    def test_encode_sequenceof(self):
        spec = sof.SequenceOf('cat', fld.Field('dog', 8, fld.Field.TEXT), 4)
        text = "<cat> <dog>a</dog> <dog>b</dog> <dog>c</dog> <dog>d</dog> </cat>"
        data = reduce(lambda a,b:a+b, xml.encode(spec, text))
        self.assertEqual("abcd", data.bytes())
