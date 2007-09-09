#!/usr/bin/env python

import unittest

import bdec
import bdec.data as dt
import bdec.entry as ent
import bdec.field as fld
import bdec.output.instance as inst
import bdec.sequence as seq
import bdec.spec.xmlspec as xml

class TestXml(unittest.TestCase):
    def test_simple_field(self):
        text = """<protocol><field name="bob" length="8" /></protocol>"""
        decoder = xml.loads(text)[0]
        self.assertTrue(isinstance(decoder, fld.Field)) 
        self.assertEqual("bob", decoder.name)
        items = list(decoder.decode(dt.Data.from_hex("7a")))
        self.assertEqual(2, len(items))
        self.assertEqual("01111010", decoder.get_value())

    def test_simple_text_field(self):
        text = """<protocol><field name="bob" length="8" type="text" /></protocol>"""
        decoder = xml.loads(text)[0]
        self.assertTrue(isinstance(decoder, fld.Field)) 
        self.assertEqual("bob", decoder.name)
        items = list(decoder.decode(dt.Data.from_hex(hex(ord('?'))[2:])))
        self.assertEqual(2, len(items))
        self.assertEqual("?", decoder.get_value())

    def test_sequence(self):
        text = """
<protocol>
    <sequence name="bob">
        <field name="cat" length="8" type="hex" />
        <field name="dog" length="8" type="integer" />
    </sequence>
</protocol>"""
        decoder = xml.loads(text)[0]
        self.assertEqual("bob", decoder.name)
        self.assertEqual("cat", decoder.children[0].name)
        self.assertEqual("dog", decoder.children[1].name)
        items = list(decoder.decode(dt.Data.from_hex("7fac")))
        self.assertEqual(6, len(items))
        self.assertEqual("7f", decoder.children[0].get_value())
        self.assertEqual(172, decoder.children[1].get_value())

    def test_bad_expected_value(self):
        text = """<protocol><field name="bob" length="8" value="0xa0" /></protocol>"""
        decoder = xml.loads(text)[0]
        self.assertEqual("bob", decoder.name)
        self.assertRaises(fld.BadDataError, lambda: list(decoder.decode(dt.Data.from_hex("7a"))))

    def test_choice(self):
        text = """
<protocol>
    <choice name="bob">
        <field name="cat" length="8" type="hex" />
        <field name="dog" length="8" type="integer" />
    </choice>
</protocol>"""
        decoder = xml.loads(text)[0]
        self.assertEqual("bob", decoder.name)
        self.assertEqual("cat", decoder.children[0].name)
        self.assertEqual("dog", decoder.children[1].name)
        items = list(decoder.decode(dt.Data.from_hex("7fac")))
        self.assertEqual(4, len(items))
        self.assertEqual("7f", decoder.children[0].get_value())

    def test_sequence_of(self):
        text = """
<protocol>
    <sequenceof name="bob" count="2">
        <field name="cat" length="8" type="hex" />
    </sequenceof>
</protocol>"""
        decoder = xml.loads(text)[0]
        self.assertEqual("bob", decoder.name)
        self.assertEqual("cat", decoder.children[0].name)
        items = list(decoder.decode(dt.Data.from_hex("7fac")))
        self.assertEqual(6, len(items))
        # We're being lazy; we're only checking the last decode value.
        self.assertEqual("ac", decoder.children[0].get_value())

    def test_non_whole_byte_expected_value(self):
        text = """<protocol><field name="bob" length="1" value="0x0" /></protocol>"""
        decoder = xml.loads(text)[0]
        self.assertEqual("bob", decoder.name)
        result = list(decoder.decode(dt.Data.from_hex("7a")))
        self.assertEqual(2, len(result))
        self.assertEqual(0, int(result[1][1]))

    def test_common(self):
        text = """<protocol> <common> <field name="bob" length="8" /> </common> <reference name="bob" /> </protocol>"""
        decoder = xml.loads(text)[0]
        self.assertEqual("bob", decoder.name)
        self.assertEqual(8, decoder.length)
        result = list(decoder.decode(dt.Data.from_hex("7a")))
        self.assertEqual(2, len(result))
        self.assertEqual(0x7a, int(result[1][1]))

    def test_common_item_references_another(self):
        text = """
            <protocol>
                <common>
                    <field name="bob" length="8" />
                    <sequence name="rabbit">
                        <reference name="bob" />
                    </sequence>
                </common>
                <reference name="rabbit" />
            </protocol>"""

        decoder = xml.loads(text)[0]
        self.assertEqual("rabbit", decoder.name)
        result = list(decoder.decode(dt.Data.from_hex("7a")))
        self.assertEqual(4, len(result))
        self.assertEqual(0x7a, int(result[2][1]))

    def test_expression_references_field(self):
        text = """
            <protocol>
                <sequence name="rabbit">
                    <field name="length:" length="8" type="integer" />
                    <field name="bob" length="${length:} * 8" type="text" />
                </sequence>
            </protocol>"""
        decoder = xml.loads(text)[0]
        result = list(decoder.decode(dt.Data("\x05hello")))
        self.assertEqual(6, len(result))
        self.assertEqual("hello", result[4][1].get_value())

    def test_empty_sequence_error(self):
        text = """<protocol><sequence name="bob"></sequence></protocol>"""
        self.assertRaises(xml.EmptySequenceError, xml.loads, text)

    def test_expression_references_sub_field(self):
        text = """
            <protocol>
                <sequence name="rabbit">
                    <sequence name="cat">
                        <field name="length:" length="8" type="integer" />
                    </sequence>
                    <field name="bob" length="${cat.length:} * 8" type="text" />
                </sequence>
            </protocol>"""
        decoder = xml.loads(text)[0]
        result = list(decoder.decode(dt.Data("\x05hello")))
        self.assertEqual("hello", result[6][1].get_value())

    def _decode(self, protocol, data):
        """
        Return a dictionary of decoded fields.
        """
        result = {}
        for is_starting, entry, entry_data, value in protocol.decode(dt.Data(data)):
            if not is_starting and isinstance(entry, fld.Field):
                result[entry.name] = entry.get_value()
        return result

    def test_expression_reference_choice_field(self):
        text = """
            <protocol>
                <sequence name="rabbit">
                    <choice name="variable length:">
                        <sequence name="8 bit:">
                           <field name="id:" length="8" value="0x0" />
                           <field name="length:" length="8" type="integer" />
                        </sequence>
                        <sequence name="16 bit:">
                           <field name="id:" length="8" value="0x1" />
                           <field name="length:" length="16" type="integer" />
                       </sequence>
                    </choice>
                    <field name="bob" length="${variable length:.length:} * 8" type="text" />
                    <!-- Now try matching the length without specifying the hidden choice -->
                    <field name="sue" length="${length:} * 8" type="text" />
                </sequence>
            </protocol>"""
        decoder = xml.loads(text)[0]

        # Try using the 8 bit length
        result = self._decode(decoder, "\x00\x05hellokitty")
        self.assertEqual("hello", result['bob'])
        self.assertEqual("kitty", result['sue'])

        # Try using the 16 bit length
        result = self._decode(decoder, "\x01\x00\x05hellokitty")
        self.assertEqual("hello", result['bob'])
        self.assertEqual("kitty", result['sue'])

    def test_not_all_choice_entries_match_error(self):
        text = """
            <protocol>
                <sequence name="rabbit">
                    <choice name="variable length:">
                        <sequence name="8 bit:">
                           <field name="id:" length="8" value="0x0" />
                           <field name="length:" length="8" type="integer" />
                        </sequence>
                        <sequence name="16 bit:">
                           <field name="id:" length="8" value="0x1" />
                           <field name="longer length:" length="16" type="integer" />
                       </sequence>
                    </choice>
                    <!-- Not all options in the choice have 'length:', so this should fail. -->
                    <field name="bob" length="${variable length:.length:} * 8" type="text" />
                </sequence>
            </protocol>"""
        try:
            xml.loads(text)
            self.fail("Exception not thrown!")
        except xml.XmlExpressionError, ex:
            self.assertTrue(isinstance(ex.ex, xml.OptionMissingNameError))

    def test_sequenceof_break(self):
        text = """
            <protocol>
                <sequenceof name="bob">
                    <choice name="char:">
                        <field name="null:" length="8" value="0x0"> <end-sequenceof /></field>
                        <field name="char" length="8" type="text" />
                    </choice>
                </sequenceof>
            </protocol>"""

        protocol = xml.loads(text)[0]
        result = ""
        for is_starting, entry, entry_data, value in protocol.decode(dt.Data("hello world\x00")):
            if not is_starting and entry.name == "char":
                result += value
        self.assertEqual("hello world", result)

    def test_length_reference(self):
        text = """
           <protocol>
               <sequence name="bob">
                   <field name="length" length="8" type="integer" />
                   <sequenceof name="null terminated string">
                       <choice name="entry:">
                           <field name="null" length="8" value="0x0" ><end-sequenceof /></field>
                           <field name="char" length="8" type="text" />
                       </choice>
                   </sequenceof>
                   <field name="unused" length="${length} * 8 - len{null terminated string}" type="text" />
               </sequence>
           </protocol>
           """
        protocol = xml.loads(text)[0]
        result = ""
        unused = ""
        for is_starting, entry, entry_data, value in protocol.decode(dt.Data("\x0fhello world\x00afd")):
            if not is_starting:
                if entry.name == "char":
                    result += value
                elif entry.name == "unused":
                    unused = entry.get_value()
        self.assertEqual("hello world", result)
        self.assertEqual("afd", unused)

    def test_field_range(self):
        text = """
            <protocol>
                <field name="bob" type="integer" length="8" min="4" max="0xf" />
           </protocol>
           """
        protocol = xml.loads(text)[0]
        self.assertRaises(fld.BadRangeError, list, protocol.decode(dt.Data('\x03')))
        self.assertRaises(fld.BadRangeError, list, protocol.decode(dt.Data('\x10')))
        self.assertEqual(4, list(protocol.decode(dt.Data('\x04')))[1][1].get_value())
        self.assertEqual(15, list(protocol.decode(dt.Data('\x0f')))[1][1].get_value())

    def test_parent_sequenceof_ends(self):
        text = """
            <protocol>
                <sequenceof name="bob">
                    <choice name="char:">
                        <field name="null:" length="8" value="0x0"> <end-sequenceof /></field>
                        <sequenceof name="dont get me" count="1">
                            <field name="char" length="8" type="text" />
                        </sequenceof>
                    </choice>
                </sequenceof>
            </protocol>"""
        protocol = xml.loads(text)[0]
        result = ""
        data = dt.Data("hello world\x00boo")
        for is_starting, entry, entry_data, value in protocol.decode(data):
            if not is_starting and entry.name == "char":
                result += value
        self.assertEqual("hello world", result)
        self.assertEqual("boo", str(data))
        
    def test_missing_reference_error(self):
        text = """
            <protocol>
                <field name="bob" length="${missing}" />
            </protocol>"""
        try:
            xml.loads(text)
            self.fail("Exception not thrown!")
        except xml.XmlExpressionError, ex:
            self.assertEqual(xml.MissingReferenceError, type(ex.ex))

    def test_sequence_value(self):
        text = """
            <protocol>
                <sequence name="buffer">
                    <sequence name="middle endian" value="${byte 1:} * 16777216 + ${byte 2:} * 65536 + ${byte 3:} * 256 + ${byte 4:}" >
                        <field name="byte 2:" length="8" />
                        <field name="byte 1:" length="8" />
                        <field name="byte 4:" length="8" />
                        <field name="byte 3:" length="8" />
                    </sequence>
                    <field name="data" length="${middle endian} * 8" type="text" />
                </sequence>
            </protocol> """
        protocol = xml.loads(text)[0]
        result = ""
        data = dt.Data("\x00\x00\x13\x00run for your lives!boo")
        for is_starting, entry, entry_data, value in protocol.decode(data):
            if not is_starting and entry.name == "data":
                result = value
        self.assertEqual("run for your lives!", result)
        self.assertEqual("boo", str(data))

    def test_match_choice_entry(self):
        text = """
            <protocol>
                <sequence name="bob">
                    <choice name="valid items:">
                        <field name="length:" length="8" value="0x5" />
                        <field name="length:" length="8" value="0x7" />
                    </choice>
                    <field name="data" length="${length:} * 8" type="text" />
                </sequence>
            </protocol>
            """
        protocol = xml.loads(text)[0]
        result = ""
        data = dt.Data("\x07chicken")
        for is_starting, entry, entry_data, value in protocol.decode(data):
            if not is_starting and entry.name == "data":
                result = value
        self.assertEqual("chicken", result)

    def test_length_validation(self):
        text = """
            <protocol>
                <sequence name="bob" length="15">
                    <field name="a" length="8" type="text" />
                    <field name="b" length="8" type="text" />
                </sequence>
            </protocol>
            """
        protocol = xml.loads(text)[0]
        result = ""
        self.assertRaises(ent.EntryDataError, list, protocol.decode(dt.Data('ab')))

    def test_common_elements_are_independant(self):
        """
        Test that decode references to common fields are used out of context.
        """
        # In this case, we want 'data a' to use the length item embedded in
        # 'length a', and not the item in 'length b'.
        text = """
            <protocol>
                <common>
                    <field name="length:" length="8" type="integer" />
                </common>
                <sequence name="bob">
                    <sequence name="length a">
                        <reference name="length:" />
                    </sequence>
                    <sequence name="length b">
                        <reference name="length:" />
                    </sequence>
                    <field name="data a" length="${length a.length:} * 8" type="text" />
                    <field name="data b" length="${length b.length:} * 8" type="text" />
                </sequence>
            </protocol>
            """
        protocol = xml.loads(text)[0]
        a = b = ""
        for is_starting, entry, entry_data, value in protocol.decode(dt.Data("\x03\x06catrabbit")):
            if not is_starting:
                if entry.name == "data a":
                    a = value
                elif entry.name == "data b":
                    b = value
        self.assertEqual("cat", a)
        self.assertEqual("rabbit", b)

    def test_delayed_referenced_common_elements_are_independant(self):
        # Here we test that so called 'delayed referenced' objects are
        # independant (ie: that an embedded referenced object doesn't
        # affect an outer object).
        text = """
            <protocol>
                <common>
                    <field name="integer" length="8" min="48" max="57" type="text" />

                    <sequence name="array">
                        <field name="opener" length="8" value="0x5b" />
                        <sequenceof name="values">
                            <choice name="entry:">
                                <field name="closer" length="8" value="0x5d"><end-sequenceof /></field>
                                <reference name="object" />
                            </choice>
                        </sequenceof>
                    </sequence>

                    <choice name="object">
                        <reference name="integer" />
                        <reference name="array" />
                    </choice>
                </common>
                <reference name="object" />
            </protocol>
            """
        protocol = xml.loads(text)[0]
        data = dt.Data("[12[34[56]7]8]unused")
        result = inst.decode(protocol, data)
        self.assertEqual("1", result.object.array.values[0].integer)
        self.assertEqual("2", result.object.array.values[1].integer)
        self.assertEqual("3", result.object.array.values[2].array.values[0].integer)
        self.assertEqual("4", result.object.array.values[2].array.values[1].integer)
        self.assertEqual("5", result.object.array.values[2].array.values[2].array.values[0].integer)
        self.assertEqual("6", result.object.array.values[2].array.values[2].array.values[1].integer)
        self.assertEqual("7", result.object.array.values[2].array.values[3].integer)
        self.assertEqual("8", result.object.array.values[3].integer)
        self.assertEqual("unused", str(data))

    def test_all_entries_in_lookup_tree(self):
        text = """
            <protocol>
                <common>
                    <choice name="dog">
                        <sequenceof name="rabbit" length="1">
                            <field name="hole" length="8" />
                        </sequenceof>
                    </choice>
                    <sequence name="length a">
                        <field name="length:" length="8" type="integer" />
                        <reference name="dog" />
                    </sequence>
                </common>
                <sequence name="bob">
                    <reference name="length a" />
                    <field name="data a" length="${length a.length:} * 8" type="text" />
                </sequence>
            </protocol>
            """
        protocol, lookup = xml.loads(text)
        entries = [protocol]
        names = set()
        while entries:
            entry = entries.pop()
            names.add(entry.name)
            self.assertTrue(entry in lookup, "%s isn't in the lookup tree!" % entry)
            entries.extend(entry.children)
        self.assertEqual(set(['dog', 'rabbit', 'hole', 'length a', 'length:', 'bob', 'data a']), names)

    def test_out_of_order_references(self):
        text = """
            <protocol>
                <common>
                    <sequence name="dog">
                        <reference name="foo" />
                    </sequence>

                    <sequence name="foo">
                        <reference name="cat" />
                    </sequence>

                    <sequence name="cat" >
                        <field name="length" length="8" type="integer" />
                    </sequence>
                </common>
                <reference name="dog" />
            </protocol>
            """
        protocol, lookup = xml.loads(text)
        for is_starting, entry, entry_data, value in protocol.decode(dt.Data('a')):
            if not is_starting and entry.name == "length":
                result = value
        self.assertEqual(ord('a'), result)

    def test_recursive_entry(self):
        text = """
            <protocol>
                <common>
                    <choice name="null terminating string:">
                        <field name="null:" length="8" value="0x0" />
                        <sequence name="non null:">
                            <field name="char" length="8" type="text" />
                            <reference name="null terminating string:" />
                        </sequence>
                    </choice>
                </common>
                <reference name="null terminating string:" />
            </protocol>
            """
        protocol, lookup = xml.loads(text)
        data = dt.Data('rabbit\0legs')
        result = ""
        for is_starting, entry, entry_data, value in protocol.decode(data):
            if not is_starting and entry.name == "char":
                result += value
        self.assertEqual("rabbit", result)
        self.assertEqual("legs", str(data))

    def test_string_constants(self):
        text = """
            <protocol>
              <sequence name="cat">
                <field name="bob" length="56" type="text" value="chicken" />
                <field name="bob" length="8" type="integer" value="73" />
              </sequence>
            </protocol>"""
        decoder = xml.loads(text)[0]
        items = list(decoder.decode(dt.Data("chicken\x49")))
        self.assertRaises(bdec.DecodeError, list, decoder.decode(dt.Data("chickan\x49")))
        self.assertRaises(bdec.DecodeError, list, decoder.decode(dt.Data("chicken\x48")))

    def test_expected_data_is_too_big(self):
        text = """
            <protocol>
              <field name="bob" length="8" value="0xFFFF" />
            </protocol>"""
        self.assertRaises(xml.XmlError, xml.loads, text)

    def test_expression_cannot_reference_common_entry(self):
        text = """
            <protocol>
              <common>
                  <field name="bob" length="8" />
                  <sequence name="hey">
                     <field name="cat" length="${bob}" />
                  </sequence>
              </common>
              <reference name="hey" />
            </protocol>"""
        self.assertRaises(xml.XmlExpressionError, xml.loads, text)

if __name__ == "__main__":
    unittest.main()
