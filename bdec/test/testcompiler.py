#   Copyright (C) 2008 Henry Ludemann
#
#   This file is part of the bdec decoder library.
#
#   The bdec decoder library is free software; you can redistribute it
#   and/or modify it under the terms of the GNU Lesser General Public
#   License as published by the Free Software Foundation; either
#   version 2.1 of the License, or (at your option) any later version.
#
#   The bdec decoder library is distributed in the hope that it will be
#   useful, but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public
#   License along with this library; if not, see
#   <http://www.gnu.org/licenses/>.


import operator
import os
import os.path
import StringIO
import unittest

import bdec.choice as chc
import bdec.compiler as comp
import bdec.data as dt
import bdec.entry as ent
import bdec.field as fld
import bdec.output.xmlout as xmlout
import bdec.sequence as seq
import bdec.sequenceof as sof
import bdec.spec.expression as expr
from bdec.test.decoders import assert_xml_equivalent, create_decoder_classes

import sys

class TestUtils(unittest.TestCase):
    def test_is_not_recursive(self):
        a = fld.Field('a', 8)
        b = fld.Field('b', 8)
        utils = comp._Utils([a, b], {})
        self.assertTrue(not utils.is_recursive(a, b))

    def test_is_recursive(self):
        a = seq.Sequence('a', [])
        b = seq.Sequence('b', [a])
        c = fld.Field('c', 8)
        d = seq.Sequence('d', [b, c])
        a.children = [d]
        utils = comp._Utils([a], {})
        self.assertTrue(utils.is_recursive(a, d))
        self.assertTrue(utils.is_recursive(b, a))
        self.assertTrue(utils.is_recursive(d, b))
        self.assertTrue(not utils.is_recursive(d, c))

class _CompilerTests:
    """
    Set of test cases to test basic compiler functionality.
    """

    def _decode_file(self, spec, common, data):
        """Return a tuple containing the exit code and the decoded xml."""
        raise NotImplementedError()


    def _decode(self, spec, data, expected_exit_code=0, expected_xml=None, common=[]):
        exit_code, xml = self._decode_file(spec, common, StringIO.StringIO(data))
        self.assertEqual(expected_exit_code, exit_code)

        if exit_code == 0:
            if expected_xml is None:
                # Take the xml output, and ensure the re-encoded data has the same
                # binary value.
                binary = reduce(lambda a,b:a+b, xmlout.encode(spec, xml)).bytes()
                self.assertEqual(data, binary)
            else:
                assert_xml_equivalent(expected_xml, xml)

    def _decode_failure(self, spec, data, common=[]):
        self._decode(spec, data, 3, common=common)

    def test_basic_decode(self):
        spec = seq.Sequence('blah', [fld.Field('hello', 8, fld.Field.INTEGER)])
        self._decode(spec, 'a')

    def test_sequence_in_sequence(self):
        spec = seq.Sequence('blah', [seq.Sequence('hello', [fld.Field('world', 8, fld.Field.INTEGER)]), fld.Field('bob', 8, fld.Field.INTEGER)])
        self._decode(spec, 'ab')

    def test_common_sequence(self):
        a = seq.Sequence('a', [fld.Field('a1', 8, fld.Field.INTEGER), fld.Field('a2', 8, fld.Field.INTEGER)])
        b = seq.Sequence('b', [a])
        spec = seq.Sequence('blah', [a, b])
        self._decode(spec, 'abcd', common=[a])

    def test_decode_string(self):
        spec = seq.Sequence('blah', [fld.Field('bob', 48, fld.Field.TEXT)])
        self._decode(spec, 'rabbit')

    def test_expected_value(self):
        spec = seq.Sequence('blah', [fld.Field('bob', 8, fld.Field.INTEGER, expected=dt.Data('a'))])
        self._decode(spec, 'a')
        self._decode_failure(spec, 'b')

    def test_binary_expected_value(self):
        spec = seq.Sequence('blah', [fld.Field('bob', 8, fld.Field.BINARY, expected=dt.Data('a'))])
        self._decode(spec, 'a')
        self._decode_failure(spec, 'b')

    def test_long_binary_expected_value(self):
        spec = seq.Sequence('blah', [fld.Field('bob', 42, fld.Field.BINARY, expected=dt.Data('abcde\xf0', start=0, end=42)), fld.Field('extra', length=6)])
        self._decode(spec, 'abcde\xf0')
        self._decode_failure(spec, 'abcde\x40')

    def test_expected_text_value(self):
        spec = seq.Sequence('blah', [fld.Field('bob', 40, fld.Field.TEXT, expected=dt.Data('hello'))])
        self._decode(spec, 'hello')
        self._decode_failure(spec, 'hella')
        self._decode_failure(spec, 'hell')

    def test_hidden_text_field_expected_value(self):
        spec = seq.Sequence('blah', [fld.Field('', 40, fld.Field.TEXT, expected=dt.Data('hello'))])
        self._decode(spec, 'hello', expected_xml="<blah/>")
        self._decode_failure(spec, 'hella')

    def test_sequence_decode_failure(self):
        spec = seq.Sequence('blah', [seq.Sequence('dog', [fld.Field('cat', 8, fld.Field.INTEGER, expected=dt.Data('a'))])])
        self._decode(spec, 'a')
        self._decode_failure(spec, 'b')

    def test_not_enough_data(self):
        spec = seq.Sequence('blah', [fld.Field('cat', 8, fld.Field.INTEGER)])
        self._decode_failure(spec, '')
        self._decode(spec, 'a')

    def test_integer_encoding(self):
        spec = seq.Sequence('blah', [fld.Field('cat', 16, fld.Field.INTEGER, encoding=fld.Field.BIG_ENDIAN)])
        self._decode(spec, 'ab')

        spec = seq.Sequence('blah', [fld.Field('cat', 16, fld.Field.INTEGER, encoding=fld.Field.LITTLE_ENDIAN)])
        self._decode(spec, 'ab')

    def test_choice(self):
        a = seq.Sequence('sue', [fld.Field('a', 8, fld.Field.INTEGER, expected=dt.Data('a'))])
        b = seq.Sequence('bob', [fld.Field('b', 8, fld.Field.INTEGER, expected=dt.Data('b'))])
        spec = chc.Choice('blah', [a, b])
        self._decode(spec, 'a')
        self._decode(spec, 'b')
        self._decode_failure(spec, 'c')

    def test_sequenceof(self):
        a = fld.Field('a', 8, fld.Field.INTEGER, expected=dt.Data('a'))
        b = fld.Field('x', 8, fld.Field.INTEGER)
        spec = sof.SequenceOf('blah', seq.Sequence('dog', [a, b]), 4)
        self._decode(spec, 'a1a2a3a4')
        self._decode(spec, 'axa8aaac')
        self._decode_failure(spec, 'a1a3a3b4')

    def test_unaligned_bits(self):
        a = fld.Field('a', 1, fld.Field.INTEGER)
        b = fld.Field('b', 3, fld.Field.INTEGER)
        c = fld.Field('c', 8, fld.Field.INTEGER)
        d = fld.Field('d', 4, fld.Field.INTEGER)
        spec = seq.Sequence('blah', [a,b,c,d])
        self._decode(spec, 'ab')

    def test_variable_length_integer(self):
        a = fld.Field('a', 8, fld.Field.INTEGER)
        value = expr.ValueResult('a')
        b = fld.Field('b', expr.Delayed(operator.__mul__, value, expr.Constant(8)), fld.Field.INTEGER)
        spec = seq.Sequence('blah', [a,b])
        expected_xml = """
           <blah>
              <a>3</a>
              <b>83</b>
           </blah> """
        self._decode(spec, '\x03\x00\x00\x53', expected_xml=expected_xml)

    def test_entry_with_multiple_outputs(self):
        # There was a problem with an entry that had multiple outputs from a
        # single child (in this test, 'c' has outputs for 'a' and 'b', both of
        # which are passed through 'problem').
        a = fld.Field('a', 8, fld.Field.INTEGER)
        b = fld.Field('b', 8, fld.Field.INTEGER)
        c = seq.Sequence('c', [a, b])
        problem = seq.Sequence('problem', [c])

        value_a = expr.ValueResult('problem.c.a')
        value_b = expr.ValueResult('problem.c.b')
        d = fld.Field('d', value_a)
        e = fld.Field('e', value_b)
        spec = seq.Sequence('spec', [problem, d, e])
        expected_xml = "<spec><problem><c><a>6</a><b>2</b></c></problem><d>111100</d><e>01</e></spec>"
        self._decode(spec, '\x06\x02\xf1', expected_xml=expected_xml)

    def test_hex_decode(self):
        a = fld.Field('a', 32, fld.Field.HEX)
        spec = seq.Sequence('blah', [a])
        self._decode(spec, 'abcd')

    def test_bits_decode(self):
        a = fld.Field('a', 6, fld.Field.INTEGER)
        b = fld.Field('b', 6, fld.Field.BINARY)
        c = fld.Field('c', 4, fld.Field.INTEGER)
        spec = seq.Sequence('blah', [a, b, c])
        self._decode(spec, 'ab')

    def test_end_sequenceof(self):
        # Note that we are wrapping the bugs in sequences because we cannot
        # store fields directly under a choice (see issue 20).
        null = seq.Sequence('fixa', [fld.Field('null', 8, fld.Field.INTEGER, expected=dt.Data('\x00'))])
        char = seq.Sequence('fixb', [fld.Field('character', 8, fld.Field.TEXT)])
        spec = sof.SequenceOf('blah', chc.Choice('byte', [null, char]), None, end_entries=[null])
        self._decode(spec, 'rabbit\0')

    def test_variable_sequenceof(self):
        a1 = fld.Field('a1', 8, fld.Field.INTEGER)
        a = seq.Sequence('a', [a1])
        value = expr.ValueResult('a.a1')

        b1 = fld.Field('b2', 8, fld.Field.INTEGER)
        ba = seq.Sequence('b1', [b1])
        b = sof.SequenceOf('b', ba, value)
        spec = seq.Sequence('blah', [a,b])
        # We don't attempt to re-encode the data, because the python encoder
        # cannot do it.
        expected_xml = """
           <blah>
              <a>
                 <a1>3</a1>
              </a>
              <b>
                 <b1><b2>0</b2></b1>
                 <b1><b2>0</b2></b1>
                 <b1><b2>83</b2></b1>
              </b>
           </blah> """
        self._decode(spec, '\x03\x00\x00\x53', expected_xml=expected_xml)

    def test_length_reference(self):
        length_total = fld.Field('length total', 8, fld.Field.INTEGER)
        total_length_expr = expr.ValueResult('length total')
        header_length = fld.Field('length header', 8, fld.Field.INTEGER)
        header_length_expr = expr.ValueResult('length header')
        header = fld.Field('header', expr.Delayed(operator.__mul__, header_length_expr, expr.Constant(8)), fld.Field.TEXT)
        header_data_length = expr.LengthResult('header')
        data_length = expr.Delayed(operator.__sub__, expr.Delayed(operator.__mul__, total_length_expr, expr.Constant(8)), header_data_length)
        data = fld.Field('data', data_length, fld.Field.TEXT)
        spec = seq.Sequence('blah', [length_total, header_length, header, data])
        expected_xml = """
           <blah>
              <length-total>10</length-total>
              <length-header>6</length-header>
              <header>header</header>
              <data>data</data>
           </blah> """
        self._decode(spec, '\x0a\x06headerdata', expected_xml=expected_xml)

    def test_fields_under_choice(self):
        a = fld.Field('a', 8, fld.Field.INTEGER, expected=dt.Data('a'))
        b = fld.Field('b', 8, fld.Field.INTEGER, expected=dt.Data('b'))
        spec = chc.Choice('blah', [a, b])
        self._decode(spec, 'a')
        self._decode(spec, 'b')
        self._decode_failure(spec, 'c')

    def test_name_escaping(self):
        a = fld.Field('a with spaces', 8, fld.Field.INTEGER)
        b = seq.Sequence('b with a ', [a])
        c = fld.Field('c', 8, fld.Field.INTEGER)
        d = seq.Sequence('d', [c])
        blah = seq.Sequence('blah', [b, d])
        self._decode(blah, 'xy', common=[blah, d])

    def test_duplicate_names_at_different_level(self):
        a = seq.Sequence('a', [fld.Field('c', 8, fld.Field.INTEGER)])
        b = seq.Sequence('b', [seq.Sequence('a', [fld.Field('d', 8, fld.Field.INTEGER)])])
        blah = seq.Sequence('blah', [a, b])
        self._decode(blah, '\x09\x06', common=[blah, a,b])

    def test_duplicate_names_in_sequence(self):
        b = seq.Sequence('a', [fld.Field('b', 8, fld.Field.INTEGER), fld.Field('b', 8, fld.Field.INTEGER)])
        blah = seq.Sequence('blah', [b])

        # We don't attempt to re-encode the data, because the python encoder
        # cannot do it (see issue41).
        expected_xml = """
           <blah>
              <a>
                 <b>9</b>
                 <b>6</b>
              </a>
           </blah> """
        self._decode(blah, '\x09\x06', expected_xml=expected_xml)

    def test_duplicate_names_in_choice(self):
        b = chc.Choice('a', [fld.Field('a', 8, fld.Field.INTEGER, expected=dt.Data('a')), fld.Field('a', 8, fld.Field.INTEGER)])
        blah = seq.Sequence('blah', [b])
        self._decode(blah, 'a')
        self._decode(blah, 'b')

    def test_duplicate_complex_embedded_entries(self):
        a = seq.Sequence('a', [seq.Sequence('a', [fld.Field('a', 8, fld.Field.INTEGER)])])
        blah = seq.Sequence('blah', [a])
        self._decode(blah, 'x')

    def test_reserved_word(self):
        a = fld.Field('int', 8, fld.Field.INTEGER)
        blah = seq.Sequence('blah', [a])
        self._decode(blah, '\x45')

    def test_duplicate_name_to_same_instance(self):
        a = fld.Field('a', 8, fld.Field.INTEGER)
        blah = seq.Sequence('blah', [a, a])

        # We don't attempt to re-encode the data, because the python encoder
        # cannot do it (see issue41).
        expected_xml = """
           <blah>
              <a>1</a>
              <a>2</a>
           </blah> """
        self._decode(blah, '\x01\x02', common=[blah, a], expected_xml=expected_xml)

    def test_min(self):
        a = fld.Field('a', 8, fld.Field.INTEGER, min=8)
        self._decode(a, '\x08')
        self._decode_failure(a, '\x07')

    def test_min_bit_buffer(self):
        a = fld.Field('a', 8, min=8)
        self._decode(a, '\x08')
        self._decode_failure(a, '\x07')

    def test_max(self):
        a = fld.Field('a', 8, fld.Field.INTEGER, max=8)
        self._decode(a, '\x08')
        self._decode_failure(a, '\x09')

    def test_recursive_entries(self):
        # There was a problem with creating include files for items that cross
        # reference each other. Test that we can create a decoder for a
        # recursive specification.
        embed_b = chc.Choice('embed b', [fld.Field('null', 8, expected=dt.Data('\x00'))])
        a = seq.Sequence('a', [fld.Field('id', 8, fld.Field.TEXT, expected=dt.Data('a')), embed_b])

        embed_a = chc.Choice('embed a', [fld.Field('null', 8, expected=dt.Data('\x00')), a])
        b = seq.Sequence('b', [fld.Field('id', 8, fld.Field.TEXT, expected=dt.Data('b')), embed_a])
        embed_b.children = list(child.entry for child in embed_b.children) + [b]

        self._decode(b, 'bababa\00', common=[a,b])
        self._decode(b, 'b\00', common=[a,b])
        self._decode_failure(b, 'bac', common=[a,b])

    def test_sequenceof_with_length(self):
        buffer = sof.SequenceOf('databuffer', fld.Field('data', 8), None, length=32)
        self._decode(buffer, 'baba')

    def test_sequenceof_failure(self):
        text = sof.SequenceOf('a', fld.Field('data', 8, expected=dt.Data('a')), count=2)
        buffer = sof.SequenceOf('databuffer', text, count=3)
        other = fld.Field('fallback', length=48)
        self._decode(chc.Choice('blah', [buffer, other]), 'aaabaa')

    def test_sequence_value(self):
        digit = seq.Sequence('digit', [fld.Field('text digit', 8, fld.Field.INTEGER, min=48, max=57)], value=expr.compile("${text digit} - 48"))
        two_digits = seq.Sequence('two digits',
                [seq.Sequence('digit 1', [digit]), seq.Sequence('digit 2', [digit])],
                value=expr.compile("${digit 1.digit} * 10 + ${digit 2.digit}"))
        buffer = fld.Field('buffer', expr.compile("${two digits} * 8"), fld.Field.TEXT)
        a = seq.Sequence('a', [two_digits, buffer])
        expected = """<a>
            <two-digits>
              <digit-1><digit><text-digit>50</text-digit></digit></digit-1>
              <digit-2><digit><text-digit>49</text-digit></digit></digit-2>
            </two-digits>
            <buffer>xxxxxxxxxxxxxxxxxxxxx</buffer>
          </a>"""
        self._decode(a, '21' + 'x' * 21, expected_xml=expected, common=[digit, two_digits, a])

    def test_hidden_sequence_with_value(self):
        digit = seq.Sequence('digit:', [fld.Field('text digit:', 8, fld.Field.INTEGER, min=48, max=57)], value=expr.compile("${text digit:} - 48"))
        a = seq.Sequence('a', [digit], value=expr.compile('${digit:} * 2'))
        self.assertTrue(digit.is_hidden())
        self._decode(a, '7', expected_xml='<a>14</a>', common=[digit, a])

    def test_empty_name(self):
        a = fld.Field('', 8, fld.Field.INTEGER, expected=dt.Data('\x00'))
        b = fld.Field('b', 8, fld.Field.INTEGER)
        c = seq.Sequence('c', [a, b])
        self._decode(c, '\x00\x10')

    def test_hidden_sequence_with_visible_children(self):
        a = fld.Field('a', 8, fld.Field.INTEGER)
        b = seq.Sequence('', [a])
        self._decode(b, '\x08')

    def test_hidden_sequence(self):
        a = fld.Field('', 8, fld.Field.INTEGER)
        b = seq.Sequence('', [a])
        c = seq.Sequence('c', [b])
        self._decode(c, '\x08', expected_xml="<c/>")

    def test_choice_hidden_child(self):
        a = fld.Field('', 8, fld.Field.INTEGER, expected=dt.Data('\x00'))
        b = fld.Field('b', 8, fld.Field.TEXT)
        c = chc.Choice('c', [a, b])
        self._decode(c, '\x00', expected_xml="<c/>")
        self._decode(c, 'x', expected_xml="<c><b>x</b></c>")

    def test_hidden_choice(self):
        a = fld.Field('a:', 8, fld.Field.INTEGER, expected=dt.Data('\x00'))
        b = fld.Field('b:', 8, fld.Field.TEXT, expected=dt.Data('x'))
        c = chc.Choice('', [a, b])
        d = seq.Sequence('d', [c])
        self._decode(d, '\x00', expected_xml="<d/>", common=[c, d])
        self._decode(d, 'x', expected_xml="<d/>", common=[c, d])
        self._decode_failure(d, 'a')

    def test_hidden_binary_field(self):
        a = fld.Field('', 0)
        b = fld.Field('b', 8)
        c = seq.Sequence('c', [a, b])
        self._decode(c, '\x00', expected_xml='<c><b>00000000</b></c>')

    def test_hidden_sequenceof(self):
        null = fld.Field('null:', 8, expected=dt.Data('\x00'))
        count = fld.Field('count:', 8, fld.Field.INTEGER)
        nulls = sof.SequenceOf('nulls:', null, expr.compile("${count:}"))
        d = seq.Sequence('d', [count, nulls])
        self._decode(d, '\x02\x00\x00', expected_xml='<d/>')
        self._decode(d, '\x03\x00\x00\x00', expected_xml='<d/>')
        self._decode_failure(d, '\x03\x00\x00')

    def test_renamed_common_entry(self):
        digit = fld.Field('digit:', format=fld.Field.INTEGER, length=8)
        number = seq.Sequence('number', [digit], value=expr.compile("${digit:} - 48") )
        header = seq.Sequence('header', [ent.Child('length', number), fld.Field('data', length=expr.compile('${length} * 8'), format=fld.Field.TEXT)])
        expected = '<header> <length>5</length> <data>abcde</data> </header>'
        self._decode(header, '5abcde', expected_xml=expected, common=[header, number])
        # Test it with not enough data
        self._decode_failure(header, '5abcd')

    def test_sequence_with_expected_length(self):
        # Test that we fail to decode when the sequence length is wrong
        a = seq.Sequence('a', [fld.Field('b', length=8)], length=expr.compile('16'))
        self._decode_failure(a, 'z')

    def test_sequenceof_with_expected_length(self):
        a = sof.SequenceOf('a', fld.Field('b', 8), None, length=expr.compile('32'))
        c = fld.Field('c', length=8, expected=dt.Data('5') )
        d = seq.Sequence('d', [a, c])
        self._decode(d, '12345')

    def test_invalid_characters_in_string(self):
        a = fld.Field('a', length=72, format=fld.Field.TEXT)
        self._decode(a, '1\x002\x013<4>5', expected_xml='<a>1?2?3&lt;4&gt;5</a>')

    def test_sequence_as_integer(self):
        # Test that we can compile non-hidden sequences with hidden children
        a = seq.Sequence('a', [fld.Field('a:', 8, fld.Field.INTEGER)], value=expr.compile("${a:}"))
        self._decode(a, '\x70', expected_xml='<a>112</a>')

    def test_common_choice_entry(self):
        # There was a bug where choice entries that referenced non-recursive
        # common entries would fail to compile.
        a = seq.Sequence('a', [fld.Field('a data', 8, fld.Field.INTEGER)])
        b = chc.Choice('b', [a])
        self._decode(b, '\x50', common=[a,b])

    def test_common_entry_in_multiple_choices(self):
        a = seq.Sequence('a', [fld.Field('a data', 8, fld.Field.INTEGER)])
        b = chc.Choice('b', [a])
        c = chc.Choice('c', [a])
        d = seq.Sequence('d', [b, c])
        self._decode(d, '\x50\x50', common=[a,b,c,d])

    def test_in_and_out_parameters(self):
        # Test what happens when we have a parameter that is to be passed out
        # of an entry, but also into a child (issue122).
        #
        #        ___ e ___
        #   __c__         d(len=a)
        #  a   b(len=a)
        a = fld.Field('a', length=8, format=fld.Field.INTEGER)
        b = fld.Field('b', length=expr.compile('${a} * 8'))
        c = seq.Sequence('c', [a, b])
        d = fld.Field('d', length=expr.compile('${c.a} * 8'))
        e = seq.Sequence('e', [c, d])
        xml = """
           <e>
             <c>
               <a>2</a>
               <b>01100001 01100001</b>
             </c>
             <d>01100010 01100010</d>
           </e>"""
        self._decode(e, '\x02aabb', common=[a,b,c,d,e], expected_xml=xml)


globals().update(create_decoder_classes([(_CompilerTests, 'SimpleDecode')], __name__))
