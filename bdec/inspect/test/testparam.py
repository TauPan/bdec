import operator
import unittest

import bdec.choice as chc
import bdec.data as dt
import bdec.field as fld
import bdec.inspect.param as prm
import bdec.sequence as seq
import bdec.sequenceof as sof
import bdec.spec.expression as expr

class TestVariableReference(unittest.TestCase):
    def test_direct_children(self):
        a = fld.Field('a', 8)
        value = expr.ValueResult('a')
        b = fld.Field('b', value)
        spec = seq.Sequence('blah', [a,b])

        vars = prm.VariableReference([spec])
        self.assertEqual(['a'], vars.get_locals(spec))
        self.assertTrue(vars.is_value_referenced(a))
        self.assertFalse(vars.is_value_referenced(b))
        self.assertEqual([], vars.get_locals(a))

    def test_sub_children(self):
        a2 = fld.Field('a2', 8)
        a1 = seq.Sequence('a1', [a2])
        a = seq.Sequence('a', [a1])
        value = expr.ValueResult('a.a1.a2')
        b1 = fld.Field('b1', value)
        b = seq.Sequence('b', [b1])
        spec = seq.Sequence('blah', [a,b])

        vars = prm.VariableReference([spec])
        self.assertEqual(['a.a1.a2'], vars.get_locals(spec))
        # Note that despite containing a referenced entry, it isn't a local (as
        # it is passed up to the parent entry).
        self.assertEqual([], vars.get_locals(a))

        # Now check what parameters are passed in and out. Note that we check
        # that the name is correct for the context of the parameter.
        self.assertEqual([], vars.get_params(spec))
        self.assertEqual([prm.Param('a2', prm.Param.OUT)], vars.get_params(a2))
        self.assertEqual([prm.Param('a2', prm.Param.OUT)], vars.get_params(a1))
        self.assertEqual([prm.Param('a1.a2', prm.Param.OUT)], vars.get_params(a))
        self.assertEqual([prm.Param('a1.a2', prm.Param.OUT)], list(vars.get_invoked_params(a, a1)))
        self.assertEqual([prm.Param('a.a1.a2', prm.Param.IN)], vars.get_params(b))
        self.assertEqual([prm.Param('a.a1.a2', prm.Param.IN)], vars.get_params(b1))
        self.assertEqual([prm.Param('a.a1.a2', prm.Param.IN)], list(vars.get_invoked_params(b, b1)))

    def test_length_reference(self):
        a1 = fld.Field('a1', 8)
        a = seq.Sequence('a', [a1])
        b1 = fld.Field('b1', expr.LengthResult('a'))
        b = seq.Sequence('b', [b1])
        spec = seq.Sequence('blah', [a,b])

        vars = prm.VariableReference([spec])
        self.assertEqual(['a length'], vars.get_locals(spec))
        self.assertFalse(vars.is_length_referenced(a1))
        self.assertTrue(vars.is_length_referenced(a))
        self.assertEqual([prm.Param('a length', prm.Param.OUT)], vars.get_params(a))
        self.assertEqual([prm.Param('a length', prm.Param.IN)], vars.get_params(b))

    def test_sequence_value(self):
        # Define an integer with a custom byte ordering
        lower = fld.Field('lower byte', 8)
        lower_value = expr.ValueResult('lower byte')
        ignored = fld.Field('ignored', 8)
        upper = fld.Field('upper byte', 8)
        upper_value = expr.ValueResult('upper byte')
        value = expr.Delayed(operator.__add__, expr.Delayed(operator.__mul__, upper_value, 256), lower_value)
        length = seq.Sequence('length', [lower, ignored, upper], value)
        header = seq.Sequence('header', [length])

        int_value = expr.ValueResult('length')
        data = fld.Field('data', int_value)
        spec = seq.Sequence('blah', [length, data])

        vars = prm.VariableReference([spec])
        self.assertEquals([], vars.get_params(spec))
        self.assertTrue(vars.is_value_referenced(lower))
        self.assertFalse(vars.is_value_referenced(ignored))
        self.assertTrue(vars.is_value_referenced(upper))
        self.assertEqual(['lower byte', 'upper byte'], vars.get_locals(length))
        self.assertEqual([prm.Param('lower byte', prm.Param.OUT)], vars.get_params(lower))
        self.assertEqual([prm.Param('upper byte', prm.Param.OUT)], vars.get_params(upper))
        self.assertEqual([prm.Param('length', prm.Param.OUT)], vars.get_params(length))

        self.assertEqual(['length'], vars.get_locals(spec))
        self.assertEqual([prm.Param('length', prm.Param.IN)], vars.get_params(data))

    def test_choice_reference(self):
        """
        Test the parameter names when we have items selected under a choice.
        """
        byte = seq.Sequence('8 bit:', [fld.Field('id', 8, expected=dt.Data('\x00')), fld.Field('length', 8)])
        word = seq.Sequence('16 bit:', [fld.Field('id', 8, expected=dt.Data('\x01')), fld.Field('length', 16)])
        length = chc.Choice('variable integer', [byte, word])
        length_value = expr.ValueResult('variable integer.length')
        data = fld.Field('data', length_value)
        spec = seq.Sequence('spec', [length, data])
        vars = prm.VariableReference([spec])

        self.assertFalse(vars.is_value_referenced(byte))
        self.assertTrue(vars.is_value_referenced(byte.children[1]))
        self.assertFalse(vars.is_value_referenced(word))
        self.assertTrue(vars.is_value_referenced(word.children[1]))
        self.assertEqual([prm.Param('length', prm.Param.OUT)], vars.get_params(byte))
        self.assertEqual([prm.Param('length', prm.Param.OUT)], vars.get_params(word))
        self.assertEqual([prm.Param('length', prm.Param.OUT)], vars.get_params(length))
        self.assertEqual([], vars.get_locals(length))
        self.assertEqual([prm.Param('length', prm.Param.OUT)], list(vars.get_invoked_params(length, byte)))

        self.assertEqual(['variable integer.length'], vars.get_locals(spec))
        self.assertEqual([prm.Param('variable integer.length', prm.Param.IN)], vars.get_params(data))

    def test_reference_outside_of_choice(self):
        """
        Test passing in a parameter into choice options.
        """
        # Note that the 'integer' option has a fixed length...
        length = fld.Field('length:', 8)
        length_value = expr.ValueResult('length:')
        text = seq.Sequence('text', [fld.Field('id:',  8, expected=dt.Data('\x00')), fld.Field('value', length_value, fld.Field.TEXT)])
        integer = seq.Sequence('integer', [fld.Field('id:',  8, expected=dt.Data('\x01')), fld.Field('value', 16, fld.Field.INTEGER)])
        spec = seq.Sequence('spec', [length, chc.Choice('data', [text, integer])])

        vars = prm.VariableReference([spec])
        self.assertTrue(vars.is_value_referenced(length))
        self.assertEqual([], vars.get_params(spec))
        self.assertEqual(['length:'], vars.get_locals(spec))
        self.assertEqual([prm.Param('length:', prm.Param.OUT)], vars.get_params(length))
        self.assertEqual([prm.Param('length:', prm.Param.OUT)], list(vars.get_invoked_params(spec, spec.children[0])))

        self.assertEqual([prm.Param('length:', prm.Param.IN)], vars.get_params(spec.children[1]))
        self.assertEqual([prm.Param('length:', prm.Param.IN)], list(vars.get_invoked_params(spec, spec.children[1])))
        self.assertEqual([prm.Param('length:', prm.Param.IN)], vars.get_params(text))
        self.assertEqual([prm.Param('length:', prm.Param.IN)], list(vars.get_invoked_params(spec.children[1], text)))
        self.assertEqual([prm.Param('length:', prm.Param.IN)], vars.get_params(text.children[1]))
        self.assertEqual([], vars.get_params(integer))
        self.assertEqual([], list(vars.get_invoked_params(spec.children[1], integer)))

    def test_unused_parameters(self):
        """
        Test detection of re-use of a common entry, where not all output parameters are used.
        """
        length = fld.Field('length', 8)
        shared = seq.Sequence('shared', [length])
        length_value = expr.ValueResult('shared.length')

        # Now we'll reference that common component twice, but only once referencing an actual value.
        a = seq.Sequence('a', [shared, fld.Field('a data', length_value)])
        b = seq.Sequence('b', [shared])
        spec = seq.Sequence('spec', [a,b])
        vars = prm.VariableReference([spec])
        self.assertEqual([], list(vars.get_params(spec)))
        self.assertTrue(vars.is_value_referenced(length))
        self.assertFalse(vars.is_value_referenced(shared))
        self.assertEqual([], vars.get_locals(spec))

        # Test that the 'length' and 'shared' entries pass out their value
        self.assertEqual([prm.Param('length', prm.Param.OUT)], list(vars.get_params(length)))
        self.assertEqual([prm.Param('length', prm.Param.OUT)], vars.get_params(shared))

        # First validate the passing of the length value within entry 'a'
        self.assertEqual([], vars.get_params(a))
        self.assertEqual(['shared.length'], vars.get_locals(a))
        self.assertEqual([prm.Param('shared.length', prm.Param.OUT)], list(vars.get_invoked_params(a, shared)))
        self.assertEqual([prm.Param('shared.length', prm.Param.IN)], list(vars.get_invoked_params(a, a.children[1])))
        self.assertEqual([], list(vars.get_invoked_params(spec, a)))

        # Now test the passing out (and ignoring) of the length value within 'b'
        self.assertEqual([], vars.get_params(b))
        self.assertEqual(['shared.length'], vars.get_locals(b))
        self.assertEqual([prm.Param('shared.length', prm.Param.OUT)], list(vars.get_invoked_params(b, shared)))
        self.assertEqual([], list(vars.get_invoked_params(spec, b)))


class TestSequenceOfParamLookup(unittest.TestCase):
    def test_end_entry_lookup(self):
        null = fld.Field("null", 8, expected=dt.Data('\x00'))
        char = fld.Field("char", 8)
        entry = chc.Choice('entry', [null, char])
        string = sof.SequenceOf("null terminated string", entry, None, end_entries=[null])

        lookup = prm.SequenceOfParamLookup([string])
        self.assertEqual(set([prm.Param('should end', prm.Param.OUT)]), lookup.get_params(null))
        self.assertEqual(set([prm.Param('should end', prm.Param.OUT)]), lookup.get_params(entry))
        self.assertEqual(['should end'], lookup.get_locals(string))
        self.assertTrue(lookup.is_end_sequenceof(null))
