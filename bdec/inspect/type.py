#   Copyright (C) 2009 Henry Ludemann
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

"""A set of classes for determining the types and range of entry parameters.
"""

import operator

from bdec.expression import Delayed, Constant, ValueResult, LengthResult

class Range:
    """A range of possible values.

    The range is inclusive. eg: min <= value <= max. If min or max is None, it
    means there is no bound in that direction.
    """
    def __init__(self, min=None, max=None):
        self.min = min
        self.max = max

    def intersect(self, other):
        """Return the intesection of self and other."""
        # max of None and X will always return X
        result = Range()
        result.min = max(self.min, other.min)
        if self.max is not None:
            if other.max is not None:
                result.max = min(self.max, other.max)
            else:
                result.max = self.max
        else:
            result.max = other.max
        return result

    def union(self, other):
        """Return the outer bounds of self and other."""
        result = Range()
        # min of None and X will always return None
        result.min = min(self.min, other.min)
        if self.max is not None and other.max is not None:
            result.max = max(self.max, other.max)
        return result

    def __eq__(self, other):
        return self.min == other.min and self.max == other.max

    def __repr__(self):
        return "[%s, %s]" % (self.min, self.max)

_ranges = {
        operator.mul : lambda left, right: Range(left.min * right.min, left.max * right.max),
        operator.div : lambda left, right: Range(left.min / right.max, left.max / right.min),
        operator.mod : lambda left, right: Range(0, right.max - 1),
        operator.add : lambda left, right: Range(left.min + right.min, left.max + right.max),
        operator.sub : lambda left, right: Range(left.min - right.max, left.max - right.min),
        }
def _delayed_range(delayed, entry, parameters):
    return _ranges[delayed.op](
            _range(delayed.left, entry, parameters),
            _range(delayed.right, entry, parameters))

def _constant_range(constant, entry, parameters):
    return Range(int(constant.value), int(constant.value))

def _reference_value_range(value, entry, parameters):
    for param in parameters.get_params(entry):
        if param.name == value.name:
            return param.type.range(parameters)
    raise Exception("Failed to find parameter '%s' in params for entry '%s'!" % (value.name, entry))

def _reference_length_range(value, entry, parameters):
    name = value.name + ' length'
    for param in parameters.get_params(entry):
        if param.name == name:
            return param.type.range(parameters)
    raise Exception("Failed to find parameter '%s' in params for entry '%s'!" % (value.name, entry))

_handlers = {
        Constant: _constant_range,
        Delayed: _delayed_range,
        ValueResult: _reference_value_range,
        LengthResult: _reference_length_range,
        }

def _range(expression, entry=None, parameters=None):
    """Return a Range instance representing the possible ranges of the expression.

    exression -- The expression to calculate the  range for.
    entry -- The entry where this expression is used. All ValueResult and
        LengthResult names are relative to this entry.
    parameters -- A bdec.inspect.param.ExpressionParameters instance, used to
        calculate the ranges of referenced entries."""
    result = _handlers[expression.__class__](expression, entry, parameters)
    return result


class VariableType:
    """Base class for all parameter types."""
    def __hash__(self):
        return hash(self.__class__)


class EntryType(VariableType):
    """Parameter value whose source is another entry."""
    def __init__(self, entry):
        self.entry = entry

    def __hash__(self):
        return hash(self.entry)

    def __eq__(self, other):
        if not isinstance(other, EntryType):
            return False
        return other.entry is self.entry


class IntegerType(VariableType):
    """Base class for describing the type of an integer."""
    def range(self, parameters):
        """Return a bdec.inspect.range.Range instance indicating the range of valid values."""
        raise NotImplementedError()


class ShouldEndType(IntegerType):
    """Parameter used to pass the 'should end' up to the parent."""
    def __eq__(self, other):
        return isinstance(other, ShouldEndType)

    def range(self, parameters):
        return Range(0, 1)


class EntryLengthType(IntegerType):
    """Parameter value whose source is the length of another entry."""
    def __init__(self, entry):
        self.entry = entry

    def __hash__(self):
        return hash(self.entry)

    def __eq__(self, other):
        return isinstance(other, EntryLengthType) and self.entry is other.entry

    def __repr__(self):
        return 'len{%s}' % self.entry

    def range(self, parameter):
        if self.entry.length is None:
            # We don't know how long this entry is.
            # FIXME: We could try examining its children...
            return Range()
        return _range(self.entry.length, self.entry ,parameter)


class EntryValueType(IntegerType):
    """Parameter value whose source is the integer value of another entry."""
    def __init__(self, entry):
        self.entry = entry

    def __hash__(self):
        return hash(self.entry)

    def __eq__(self, other):
        return isinstance(other, EntryValueType) and self.entry is other.entry

    def range(self, parameters):
        import bdec.field as fld
        import bdec.sequence as seq
        if isinstance(self.entry, fld.Field):
            length_range = _range(self.entry.length, self.entry, parameters)
            result = Range(0, pow(2, length_range.max) - 1)
        elif isinstance(self.entry, seq.Sequence):
            result = _range(self.entry.value, self.entry, parameters)

        for constaint in self.entry.constraints:
            result = result.intersect(constaint.range(parameters))
        return result


class MultiSourceType(IntegerType):
    """Parameter whose value comes from multiple locations."""
    def __init__(self, sources):
        for source in sources:
            assert isinstance(source, VariableType)
        self.sources = sources

    def __eq__(self, other):
        if not isinstance(other, MultiSourceType):
            return False
        if len(self.sources) != len(other.sources):
            return False
        for a, b in zip(self.sources, other.sources):
            if a != b:
                return False
        return True

    def range(self, parameters):
        range = Range()
        for source in self.sources:
            range = range.union(source)
        return range



class ExpressionRanges:
    """A class to evaluate the possible ranges of an integer expression."""
    def __init__(self, entries):
        # TODO: Use the expression parameter inspection to determine the
        # sources of the expression paramters, and use that (combined with
        # the 'range' method') to determine the possible integer range for
        # any given expression value.
        pass

