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
import string

import bdec.choice as chc
from bdec.constraints import Equals
from bdec.data import Data
from bdec.encode import get_encoder
from bdec.entry import Entry
from bdec.inspect.solver import solve_expression
import bdec.field as fld
import bdec.sequence as seq
from bdec.sequenceof import SequenceOf
from bdec.expression import ArithmeticExpression, ReferenceExpression, Constant
from bdec.inspect.param import Local, Param, MAGIC_UNKNOWN_NAME
from bdec.inspect.type import EntryLengthType, EntryValueType, IntegerType, EntryType, expression_range

keywords=['char', 'int', 'short', 'long', 'float', 'if', 'then', 'else', 'struct', 'for', 'null', 'signed', 'true', 'false']

# Also define our types as keywords, as we don't want the generated names to
# clash with our types.
keywords += ['Buffer', 'Text', 'BitBuffer']

unsigned_types = {'unsigned int':(32, '%u'), 'unsigned long long':(64, '%llu')}
signed_types = {'int':(32, '%i'), 'long long':(64, '%lli')}

def is_numeric(type):
    if type == 'unsigned char':
        # We have an explicit unsigned char for short bitfields
        return True
    return type in signed_types or type in unsigned_types

def printf_format(type):
    a = unsigned_types.copy()
    a.update(signed_types)
    return a[type][1]

_escaped_types = {}
def escaped_type(entry):
    if not _escaped_types:
        # Create a cache of names to types (this function is called many times).
        embedded = [e for e in iter_entries() if e not in common]
        entries = common + embedded

        common_names = [e.name for e in common]
        embedded_names = [e.name for e in embedded]

        # We escape the 'common' entries first, so they can get as close a name
        # as possible to their unescaped name.
        names = esc_names(common_names, esc_name)
        names += esc_names(embedded_names, esc_name, names)
        _escaped_types.update(zip(entries, names))
    return _escaped_types[entry]

def _int_types():
    possible = [(name, -1 << (info[0] - 1), (1 << (info[0] - 1)) - 1) for name, info in signed_types.items()]
    possible.extend((name, 0, (1 << info[0]) - 1) for name, info in unsigned_types.items())
    possible.sort(key=lambda a:a[2])
    for name, minimum, maximum in possible:
        yield name, minimum, maximum

def _biggest(types):
    """ Return the biggest possible type."""
    return reduce(lambda a, b: a if a[1][0] > b[1][0] else b, types.items())[0]

def _integer_type(type):
    """Choose an appropriate integral type for the given type."""
    return _type_from_range(type.range(raw_params))

def _type_from_range(range):
    if range.min is None:
        # This number doesn't have a minimum value; choose the type that can
        # represent the most negative number.
        return _biggest(signed_types)
    if range.max is None:
        # This number doesn't have a maximum valuea; choose the type that can
        # represent the largest number.
        return _biggest(unsigned_types)

    for name, minimum, maximum in _int_types():
        if range.min >= minimum and range.max <= maximum:
            return name

    # We don't have big enough type for this number...
    return _biggest(signed_types)

def get_integer(entry):
    """ Choose either the 'int' or the 'long long' decoder.

    entry -- The entry we are decoding. Looks at it's possible length when
        deciding which decode function to use.
    """
    if EntryValueType(entry).range(raw_params).max <= 0xffffffff:
        return 'get_integer'
    else:
        return 'get_long_integer'

def children_contain_data(entry):
    for child in entry.children:
        if child_contains_data(child):
            return True
    return False

def _entry_type(entry):
    assert isinstance(entry, Entry), "Expected an Entry instance, got '%s'!" % entry
    if isinstance(entry, fld.Field):
        if entry.format == fld.Field.INTEGER:
            return _integer_type(EntryValueType(entry))
        if entry.format == fld.Field.TEXT:
            return 'Text'
        elif entry.format == fld.Field.HEX:
            return 'Buffer'
        elif entry.format == fld.Field.BINARY:
            range = EntryLengthType(entry).range(raw_params)
            if range.min is not None and range.min == range.max and range.min <= 8:
                # If we have a fixed size buffer, stash it in an integer. We
                # only allow bitstrings under a 'char', otherwise we start
                # getting endian issues....
                return 'unsigned char'
            return 'BitBuffer'
        elif entry.format == fld.Field.FLOAT:
            range = EntryLengthType(entry).range(raw_params)
            if range.max is not None and range.max == 32:
                return 'float'
            else:
                return 'double'
        else:
            raise Exception("Unhandled field format '%s'!" % entry)
    elif isinstance(entry, seq.Sequence) and entry.value is not None and \
            not children_contain_data(entry):
        # This sequence has hidden children and a value; we can treat this as
        # an integer.
        return _integer_type(EntryValueType(entry))
    elif isinstance(entry, chc.Choice) and not children_contain_data(entry):
        return 'enum %s' % enum_type_name(entry)
    else:
        return "struct " + typename(escaped_type(entry))

def ctype(variable):
    """Return the c type name for an entry"""
    if isinstance(variable, Entry):
        return _entry_type(variable)
    elif isinstance(variable, EntryType):
        return _entry_type(variable.entry)
    elif isinstance(variable, IntegerType):
        return _integer_type(variable)
    else:
        raise Exception("Unknown parameter type '%s'!" % variable)

def _get_param_string(params):
    result = ""
    for param in params:
        if param.direction is param.IN:
            type = ctype(param.type)
            pointer = '*' if not is_numeric(type) else ''
            result += ", %s%s %s" % (type, pointer, param.name)
        else:
            result += ", %s* %s" % (ctype(param.type), param.name)
    return result

def define_params(entry):
    return _get_param_string(get_params(entry))

def encode_params(entry):
    return _get_param_string(encode_params.get_params(entry))

def option_output_temporaries(entry, child_index, params):
    """Return a dictionary of {name : temp_name}.

    This maps the option entries name to a local's name. This is done because
    each of the options may have a different type for the same named output
    (for example, the different options may be of type int, unsigned char,
    long long...) meaning we cannot pass the choice's output directly by
    pointer.
    """
    # If we are a choice entry, a single output parameter of the choice
    # may come from one of multiple types of children, each of which might
    # have a different integer type (eg: byte, int, long long). To handle this
    # we use local variables for all outputs from a choice, before assigning
    # them to the 'real' output at the end.
    assert isinstance(entry, chc.Choice)
    result = {}
    param_names = [param.name for param in params.get_params(entry)]
    param_names.extend(local.name for local in params.get_locals(entry))

    for param in params.get_passed_variables(entry, entry.children[child_index]):
        if param.direction == param.OUT and param.name in param_names:
            # We found a parameter that is output from the entry; to
            # avoid the possibility that this is a different type to
            # the parent output, we stash it in a temporary location.
            result[param.name] = '%s%i' % (param.name, child_index)
    return result

def _locals(entry, params):
    for local in params.get_locals(entry):
        yield local
    if isinstance(entry, chc.Choice):
        for i, child in enumerate(entry.children):
            lookup = option_output_temporaries(entry, i, params)
            for param in get_passed_variables(entry, entry.children[i]):
                try:
                    # Create a temporary local for this parameter...
                    yield Local(lookup[param.name], param.type)
                except KeyError:
                    # This variable isn't output from the choice...
                    pass

def local_variables(entry):
    return _locals(entry, decode_params)

def encode_local_variables(entry):
    return _locals(entry, encode_params)

def _passed_variables(entry, child_index, params):
    temp = {}
    if isinstance(entry, chc.Choice):
        temp = option_output_temporaries(entry, child_index, params)

    for param in params.get_passed_variables(entry, entry.children[child_index]):
        try:
            # First check to see if the parameter is one that we map locally...
            yield Param(temp[param.name], param.OUT, param.type)
        except KeyError:
            yield param

def is_pointer(name, entry, params):
    """Check to see if a local variable or a parameter is a pointer.

    name -- The name of the local variable / parameter
    entry -- The entry containing the variable / parameter
    params -- A _Parameters instance.
    """
    # If the parameter is an output parameter, it must be a pointer.
    if name in (p.name for p in params.get_params(entry) if p.direction == p.OUT):
        return True
    # If it's an input (but is of a complex type), it's also passed as a
    # pointer.
    complex_types = list(p.name for p in params.get_params(entry) if not is_numeric(ctype(p.type)))
    return name in complex_types

def _value_ref(name, entry, params):
    if is_pointer(name, entry, params):
        return '*%s' % name
    return name

def _call_params(parent, i, result_name, params):
    # How we should reference the variable passed to the child is from the
    # following table;
    #
    #                        Child in   |   Child out
    #                       --------------------------
    # Local or input param |    name    |    &name    |
    #                      |--------------------------|
    #         Output param |   *name    |    name     |
    #                       --------------------------
    result = ""
    for param in _passed_variables(parent, i, params):
        if param.direction == param.OUT:
            expects_pointer = True
        else:
            # In parameters expect a pointer for complex types...
            expects_pointer = not is_numeric(ctype(param.type))

        is_local_pointer = is_pointer(param.name, parent, params)
        local_name = param.name
        if param.name == MAGIC_UNKNOWN_NAME:
            # All 'magic' parameters (ie: those that represent the child's
            # value, not just references it will use) are pointers.
            is_local_pointer = True
            local_name = result_name

        if expects_pointer == is_local_pointer:
            # If both us & the child are the same, just pass it through
            result += ', %s' % local_name
        elif expects_pointer:
            result += ', &%s' % local_name
        else:
            result += ', *%s' % local_name
    return result

def decode_passed_params(parent, i, result_name):
    return _call_params(parent, i, result_name, decode_params)

def encode_passed_params(parent, i, result_name):
    return _call_params(parent, i, result_name, encode_params)

_OPERATORS = {
        operator.__div__ : '/', 
        operator.__mod__ : '%',
        operator.__mul__ : '*',
        operator.__sub__ : '-',
        operator.__add__ : '+',
        operator.lshift : '<<',
        operator.rshift : '>>',
        }

def value(entry, expr, params=None, magic_expression=None, magic_name=None):
  """
  Convert an expression object to a valid C expression.

  entry -- The entry that will use this value.
  expr -- The bdec.expression.Expression instance to represent in C code.
  params -- The parameters to use for finding variables. If None, it will use
    the decode parameters (decode_params).
  magic_expression -- If the 'magic_expression' is found it will be replaced
    with the 'magic_name'.
  magic_name -- The 'magic' name to use when 'magic_expression' is found.
  """
  if params is None:
      params = decode_params
  if expr is magic_expression:
      return magic_name
  elif isinstance(expr, int):
      return str(expr)
  elif isinstance(expr, Constant):
      if expr.value >= (1 << 32):
          return "%iLL" % expr.value
      elif expr.value > (1 << 31):
          return "%iL" % expr.value
      return int(expr.value)
  elif isinstance(expr, ReferenceExpression):
      return _value_ref(local_name(entry, expr.param_name()), entry, params)
  elif isinstance(expr, ArithmeticExpression):
      left = value(entry, expr.left, params, magic_expression, magic_name)
      right = value(entry, expr.right, params, magic_expression, magic_name)

      cast = ""
      left_type = _type_from_range(expression_range(expr.left, entry, raw_params))
      right_type = _type_from_range(expression_range(expr.right, entry, raw_params))
      result_type = _type_from_range(expression_range(expr, entry, raw_params))

      types = unsigned_types.copy()
      types.update(signed_types)
      if types[result_type][0] > max(types[left_type][0], types[right_type][0]):
          # If the result will be bigger than both left and right, we will
          # explicitly cast to make sure the operation is valid. For example,
          # '1 << 63' is invalid, but '(long long)1 << 63' is ok.
          cast = "(%s)" % result_type
      return "(%s%s %s %s)" % (cast, left, _OPERATORS[expr.op], right)
  else:
      raise Exception('Unknown length value', expr)

def enum_type_name(entry):
    return typename(settings.escaped_type(entry) + ' option')

_enum_cache = {}
def enum_value(parent, child_index):
    if not _enum_cache:
        # For all global 'options', we need the enum item to be unique. To do
        # this we get all possible options, then get a unique name for that
        # option.
        options = []
        offsets = {}
        for e in iter_entries():
            if isinstance(e, chc.Choice):
                offsets[e] = range(len(options), len(options) + len(e.children))
                options.extend(c.name for c in e.children)
        names = esc_names(options, constant)
        for e in iter_entries():
            if isinstance(e, chc.Choice):
                _enum_cache[e] = list(names[i] for i in offsets[e])
    return _enum_cache[parent][child_index]

def decode_name(entry):
    return function('decode ' + escaped_type(entry))

def print_name(entry):
    return function('print xml ' + escaped_type(entry))

def encode_name(entry):
    return function('encode ' + escaped_type(entry))

_var_name_cache = {}
def var_name(entry, child_index):
    try:
        names = _var_name_cache[entry]
    except KeyError:
        names = esc_names((c.name for c in entry.children), variable)
        _var_name_cache[entry] = names
    return names[child_index]

def free_name(entry):
    return function('free ' + escaped_type(entry))

_PRINTABLE = string.ascii_letters + string.digits
def _c_repr(char):
    if char in _PRINTABLE:
        return char
    return '\\%03o' % ord(char)

def c_string(data):
    """Return a correctly quoted c-style string for an arbitrary binary string."""
    return '"%s"' % ''.join(_c_repr(char) for char in data)

def _get_equals(entry):
    for constraint in entry.constraints:
        if isinstance(constraint, Equals):
            return constraint.limit

def _are_expression_inputs_available(expr, entry):
    """Check to see if all of the inputs to an expression are available."""
    names = [p.name for p in encode_params.get_params(entry) if p.direction == p.IN]

    result = ReferenceExpression('result')
    inputs = [p.name for p in encode_params.get_params(entry) if p.direction == p.IN]
    constant, components = solve_expression(result, expr, entry, raw_decode_params, inputs)
    for ref, expr, inverted in components:
        if variable(ref.name) not in names:
            # The expression references an item that isn't being passed in.
            return False
    return True

def get_sequence_value(entry):
    """Get a sequences value when encoding.

    Returns a (value, should_solve) tuple."""
    # When we have an expected value, we should using that as the value to solve...
    should_solve = True
    in_params = [p.name for p in encode_params.get_params(entry) if p.direction == p.IN]
    if contains_data(entry):
        # This entry is visible; use its 'value' input.
        value_name = 'value' if is_numeric(ctype(entry)) else 'value->value'
    elif variable(entry.name) in in_params:
        # This entry has been referenced elsewhere, and it's value is
        # being passed as an exression.
        value_name = variable(entry.name)
    elif _are_expression_inputs_available(entry.value, entry):
        # All of the components of this entrie's value are being passed in (ie:
        # we can determine its value)
        value_name = value(entry, entry.value)
    elif _get_equals(entry) is not None:
        # This entry has an expected value
        value_name = _get_equals(entry)
    else:
        # We cannot determine the value of this entry! It's probably being
        # derived from child values.
        # This isn't being passed in an input parameter! Presumably
        # it is has a fixed value, or is derived from other values...
        should_solve = False
        value_name = value(entry, entry.value)
    return value_name, should_solve

def get_expected(entry):
    value = _get_equals(entry)
    if value is not None:
        if entry.format == fld.Field.INTEGER:
            return value
        elif entry.format == fld.Field.TEXT:
            return '{"%s", %i}' % (value.value, len(value.value))
        elif entry.format == fld.Field.BINARY:
            if settings.is_numeric(settings.ctype(entry)):
                # This is an integer type
                return value
            else:
                # This is a bitbuffer type; add leading null bytes so we can
                # represent it in bytes.
                null = Data('\x00', 0, 8 - (len(value.value) % 8))
                data = null + value.value
                result = '{(unsigned char*)%s, %i, %i}' % (
                        c_string(data.bytes()), len(null),
                        len(data) - len(null))
                return result
        else:
            raise Exception("Don't know how to define a constant for %s!" % entry)

def get_null_mock_value(entry):
    # The entry is hidden, so use a \x00 (null) value.
    length = entry.length.evaluate({})
    if entry.format == fld.Field.INTEGER:
        return 0
    elif entry.format == fld.Field.TEXT:
        return '{"%s", %i}' % ('\\000' * (length / 8), length / 8)
    elif entry.format == fld.Field.BINARY:
        if settings.is_numeric(settings.ctype(entry)):
            # This is an integer type
            return 0
        else:
            # This is a bitbuffer type
            return '{(unsigned char*)"%s", 0, %i}' % ('\\000' * ((length + 7) / 8), length)
    else:
        raise Exception("Don't know how to define a constant for %s!" % entry)


def is_empty_sequenceof(entry):
    return isinstance(entry, SequenceOf) and not contains_data(entry)

def set_mock_param(entry, i, param, child_variable):
    """ Return an expression setting the parameter value in the mock object.

    Mock objects are used when visible common entries are hidden locally; to
    encode these we have to construct a temporary mock instance, populating
    the parameters as necessary. This function is responsible for setting the
    parameters within the mock object."""
    child = entry.children[i]
    for i, p in enumerate(stupid_ugly_expression_encode_params.get_passed_variables(entry, child)):
        if p.name == param.name:
            break
    else:
        raise Exception('Failed to find param %s!' % param)
    raw_param = raw_encode_expression_params.get_passed_variables(entry, child)[i]
    # Note: This only works if the referenced item is sequences! If we're
    # referencing a choice, we should be setting 'choice.value.xxx'.
    names = list(variable(p) for p in raw_param.name.split('.'))
    names[0] = child_variable
    return '%s = %s;' % ('.'.join(names), param.name)

def sequence_encoder_order(entry):
    """Return the order we should be encoding the child entries in a sequence.

    Returns a iterable of (child_offset, start_temp_buffer, buffer_name, end_temp_buffers)
    tuples."""
    result_offset = 0
    temp_buffers = []
    encoder = get_encoder(entry, raw_encode_expression_params)
    for child_encoder in encoder.order():
        child = child_encoder.child
        i = entry.children.index(child)

        start_temp_buffer = None
        if i == result_offset:
            # We can encode this entry directly into the result buffer
            buffer_name = 'result'
            result_offset += 1
        else:
            # This entry must be buffered (it cannot be directly appended onto result)
            for b in  temp_buffers:
                if b['end'] == i:
                    # We found an existing temporary buffer we can append to
                    temp_buffer = b
                    break
            else:
                # There isn't an existing temporary buffer we can reuse; create a new one.
                temp_buffer = {'name':'tempBuffer%i' % len(temp_buffers), 'start':i, 'end':i}
                temp_buffers.append(temp_buffer)
            temp_buffer['end'] += 1
            buffer_name = '&%s' % temp_buffer['name']

            if temp_buffer['start'] == i:
                # We found a temporary buffer that starts here
                start_temp_buffer = temp_buffer['name']

        # Check for temporary buffers that start here; not that there can be
        # several temp buffers that need to be chained together (see the
        # xml/089_length_reference regression test).
        end_temp_buffers = []
        should_stop = False
        while not should_stop:
            for temp_buffer in temp_buffers:
                if temp_buffer['start'] == result_offset:
                    # We found a temporary buffer that ends here
                    end_temp_buffers.append(temp_buffer['name'])
                    result_offset = temp_buffer['end']
                    break
            else:
                should_stop = True
        yield i, start_temp_buffer, buffer_name, end_temp_buffers

