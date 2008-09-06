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

#!/usr/bin/env python
import unittest

import bdec.choice as chc
import bdec.data as dt
import bdec.field as fld
import bdec.sequence as seq
import bdec.sequenceof as sof

class TestSequenceOf(unittest.TestCase):
    def test_sequence_of_field(self):
        sequenceof = sof.SequenceOf("blah", fld.Field("cat", 8, fld.Field.INTEGER), 3)

        actual = []
        for is_starting, entry, entry_data, value in sequenceof.decode(dt.Data.from_hex("fb028c")):
            if not is_starting:
                data = value
                actual.append((entry.name, data))

        expected = [("cat", 0xfb),
            ("cat", 0x02),
            ("cat", 0x8c),
            ("blah", None)]
        self.assertEqual(expected, actual)

    def test_encoding(self):
        sequenceof = sof.SequenceOf("blah", fld.Field("cat", 8, format=fld.Field.INTEGER), 3)
        data = {"blah" : [{"cat":5}, {"cat":9}, {"cat":0xf6}]}
        query = lambda context, child: context[child.name] 
        data = reduce(lambda a,b:a+b, sequenceof.encode(query, data))
        self.assertEqual("\x05\x09\xf6", data.bytes())

    def test_invalid_encoding_count(self):
        sequenceof = sof.SequenceOf("blah", fld.Field("cat", 8, format=fld.Field.INTEGER), 3)
        data = {"blah" : [{"cat":5}, {"cat":9}]}
        query = lambda context, child: context[child.name] 
        self.assertRaises(sof.InvalidSequenceOfCount, list, sequenceof.encode(query, data))

    def test_greedy_decode(self):
        sequenceof = sof.SequenceOf("blah", fld.Field("cat", 8, format=fld.Field.TEXT), None, length=32)
        rawdata = dt.Data("dateunused")
        items = [value for is_starting, entry, data, value in sequenceof.decode(rawdata) if isinstance(entry, fld.Field) and not is_starting]
        self.assertEqual(4, len(items))
        self.assertEqual('date', ''.join(items))
        self.assertEqual('unused', rawdata.bytes())

    def test_run_out_of_data_greedy(self):
        sequenceof = sof.SequenceOf("blah", fld.Field("cat", 8, format=fld.Field.TEXT), None, length=32)
        rawdata = dt.Data("date")
        items = [value for is_starting, entry, data, value in sequenceof.decode(rawdata) if isinstance(entry, fld.Field) and not is_starting]
        self.assertEqual(4, len(items))
        self.assertEqual('date', ''.join(items))
        self.assertEqual('', rawdata.bytes())

    def test_encoding_greedy_sequenceof(self):
        sequenceof = sof.SequenceOf("blah", fld.Field("cat", 8, format=fld.Field.INTEGER), None)
        data = {"blah" : [{"cat":5}, {"cat":9}, {"cat":0xf6}]}
        query = lambda context, child: context[child.name] 
        data = reduce(lambda a,b:a+b, sequenceof.encode(query, data))
        self.assertEqual("\x05\x09\xf6", data.bytes())

    def test_negative_count(self):
        sequenceof = sof.SequenceOf("blah", fld.Field("cat", 8, format=fld.Field.INTEGER), -1)
        self.assertRaises(sof.NegativeSequenceofLoop, list, sequenceof.decode(dt.Data("")))

    def test_end_entries(self):
        null = fld.Field("null", 8, expected=dt.Data('\x00'))
        char = fld.Field("char", 8)
        sequenceof = sof.SequenceOf("null terminated string", chc.Choice('entry', [null, char]), None, end_entries=[null])
        actual = []
        data = dt.Data("hello\x00bob")
        result = ""
        for is_starting, entry, entry_data, value in sequenceof.decode(data):
            if not is_starting and entry.name == "char":
                result += entry_data.bytes()

        self.assertEqual("hello", result)
        self.assertEqual("bob", data.bytes())
