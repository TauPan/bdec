## vim:set syntax=mako:

<%! 
  from bdec.choice import Choice
  from bdec.constraints import Equals
  from bdec.data import Data
  from bdec.expression import Constant
  from bdec.field import Field
  from bdec.sequence import Sequence
  from bdec.sequenceof import SequenceOf
 %>

/*  Portions Copyright (C) 2008-2009 Henry Ludemann

    This file is part of the bdec decoder library.

    The bdec decoder library is free software; you can redistribute it
    and/or modify it under the terms of the GNU Lesser General Public
    License as published by the Free Software Foundation; either
    version 2.1 of the License, or (at your option) any later version.

    The bdec decoder library is distributed in the hope that it will be
    useful, but WITHOUT ANY WARRANTY; without even the implied warranty
    of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public
    License along with this library; if not, see
    <http://www.gnu.org/licenses/>. */

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "${entry.name |filename}.h"
%for e in iter_optional_common(entry):
#include "${e.name |filename}.h"
%endfor
#include "variable_integer.h"

<%def name="compare_binary_expected(entry, expected)">
  %if expression_range(expected).max is not None and expression_range(expected).max < 2^64:
    if (get_integer(&value) != ${settings.value(entry, expected)})
  %else:
    ## NOTE: We are assuming that if a constraint is longer than a long int, it
    ## is a constant constraint.
    <% assert isinstance(expected, Constant) %>
    <% padding_len = (8 - len(expected.value) % 8) if len(expected.value) % 8 <  8 else 0 %>
    <% data = expected.value + Data('\x00', 0, padding_len) %>
    BitBuffer expected = {(unsigned char*)${settings.c_string(data.bytes())}, 0, ${len(expected.value)}};
    int isMatch = 1;
    BitBuffer actual = value;
    while (expected.num_bits > 0)
    {
        if (decode_integer(&expected, 1) != decode_integer(&actual, 1))
        {
            isMatch = 0;
            break;
        }
    }
    if (!isMatch)
  %endif
</%def>

<%def name="checkConstraints(entry, value, result)">
  %for constraint in entry.constraints:
    %if isinstance(constraint, Equals):
      %if settings.is_numeric(settings.ctype(entry)) or isinstance(entry, Sequence):
    if (${value} != ${settings.value(entry, constraint.limit)})
      %elif settings.ctype(entry) == 'BitBuffer':
    ${compare_binary_expected(entry, constraint.limit)}
      %elif settings.ctype(entry) in ['Buffer', 'Text']:
      <% assert isinstance(constraint.limit, Constant) %>
      <% expected = entry.encode_value(constraint.limit.value) %>
    if (${value}.length != ${len(expected) / 8} ||
            memcmp(${value}.buffer, ${settings.c_string(expected.bytes())}, ${len(expected) / 8}) != 0)
      %else:
      <%raise Exception("Don't know how to compare '%s' types for equality in entry '%s'!" % (constraint, entry)) %>
      %endif
    %else:
      ## For all constraints other than equality we treat the value as an integer...
      %if settings.is_numeric(settings.ctype(entry)):
    if (${value} ${constraint.type} ${settings.value(entry, constraint.limit)})
      %elif settings.ctype(entry) == 'BitBuffer':
    if (${get_integer(entry)}(&${value}) ${constraint.type} ${str(constraint.limit)})
      %elif settings.ctype(entry) in ['Buffer', 'Text']:
    if (${value}.length != 1 || (unsigned int)${value}.buffer[0] ${constraint.type} ${str(constraint.limit)})
      %else:
      <%raise Exception("Don't know how to compare '%s' types!" % constraint) %>
      %endif
    %endif
    {
      %if contains_data(entry) or (isinstance(entry, Field) and entry.format != Field.INTEGER):
        ${settings.free_name(entry)}(${result});
      %endif
        return 0;
    }
  %endfor
</%def>

<%def name="decodeField(entry)">
    ${settings.ctype(entry)} value;
  %if settings.is_numeric(settings.ctype(entry)):
    %if entry.encoding == Field.LITTLE_ENDIAN:
    value = decode_little_endian_integer(buffer, ${settings.value(entry, entry.length)});
    %else:
      %if EntryValueType(entry).range(raw_params).max <= 0xffffffff:
    value = decode_integer(buffer, ${settings.value(entry, entry.length)});
      %else:
    value = decode_long_integer(buffer, ${settings.value(entry, entry.length)});
      %endif
    %endif
    %if is_value_referenced(entry):
    *${entry.name |variable} = value;
    %endif
  %elif entry.format == Field.TEXT:
    unsigned int i;
    value.length = ${settings.value(entry, entry.length)} / 8;
    value.buffer = (char*)malloc(value.length + 1);
    value.buffer[value.length] = 0;
    for (i = 0; i < value.length; ++i)
    {
        value.buffer[i] = decode_integer(buffer, 8);
    }
  %elif entry.format == Field.HEX:
    unsigned int i;
    assert((${settings.value(entry, entry.length)}) % 8 == 0);
    value.length = ${settings.value(entry, entry.length)} / 8;
    value.buffer = (unsigned char*)malloc(value.length);
    for (i = 0; i < value.length; ++i)
    {
        value.buffer[i] = decode_integer(buffer, 8);
    }
  %elif entry.format == Field.BINARY:
    value.start_bit = buffer->start_bit;
    value.num_bits = ${settings.value(entry, entry.length)};
    unsigned int numBytes = (buffer->start_bit + buffer->num_bits + 7) / 8;
    value.buffer = (unsigned char*)malloc(numBytes);
    memcpy(value.buffer, buffer->buffer, numBytes);
    buffer->start_bit += value.num_bits;
    buffer->buffer += buffer->start_bit / 8;
    buffer->start_bit %= 8;
    buffer->num_bits -= value.num_bits;

    %if is_value_referenced(entry):
    *${entry.name |variable} = ${get_integer(entry)}(&value);
    %endif
  %elif entry.format == Field.FLOAT:
    <% encoding = 'BDEC_LITTLE_ENDIAN' if entry.encoding == Field.LITTLE_ENDIAN \
         else 'BDEC_BIG_ENDIAN' %>

    switch (${settings.value(entry, entry.length)})
    {
    case 32:
        value = decodeFloat(buffer, ${encoding});
        break;
    case 64:
        value = decodeDouble(buffer, ${encoding});
        break;
    default:
        return 0;
    }
  %else:
    <% raise Exception('Unknown field type %s' % entry) %>
  %endif
    ${checkConstraints(entry, 'value', '&value')}
    %if contains_data(entry):
    (*result) = value;
    %else:
      %if entry.format != Field.INTEGER:
    ${settings.free_name(entry)}(&value);
      %endif
    %endif
</%def>

<%def name="decodeSequence(entry)">
    %for i, child in enumerate(entry.children):
    if (!${settings.decode_name(child.entry)}(buffer${settings.call_params(entry, i, '&result->%s' % settings.var_name(entry, i))}))
    {
        %for j, previous in enumerate(entry.children[:i]):
            %if child_contains_data(previous):
        ${settings.free_name(previous.entry)}(&result->${settings.var_name(entry, j)});
            %endif
        %endfor
        return 0;
    }
    %endfor
    %if entry.value is not None:
    ${ctype(EntryValueType(entry))} value = ${settings.value(entry, entry.value)};
    ${checkConstraints(entry, 'value', 'result')}
      %if contains_data(entry):
        %if settings.is_numeric(settings.ctype(entry)):
    *result = value;
        %else:
    result->value = value;
        %endif
      %endif
      %if is_value_referenced(entry):
    *${entry.name |variable} = value;
      %endif
    %endif
</%def>

<%def name="decodeSequenceOf(entry)">
    <% child_type = settings.ctype(entry.children[0].entry) %>
    %if entry.end_entries:
    ${'should end'|variable} = 0;
    %endif

    %if entry.count is not None:
    ## There is a 'count' avaiable; use that to allocate the buffer up front.
    unsigned int i;
    unsigned int num_items;
    num_items = ${settings.value(entry, entry.count)};
      %if contains_data(entry):
    result->count = num_items;
        %if child_contains_data(entry.children[0]):
    result->items = (${child_type}*)malloc(sizeof(${child_type}) * result->count);
        %endif
      %endif
    for (i = 0; i < num_items; ++i)
    {
    %else:
      ## There isn't a count, so keep decoding until we run out of data.
      %if contains_data(entry):
    unsigned int i;
        %if child_contains_data(entry.children[0]):
    result->items = 0;
        %endif
    result->count = 0;
      %endif
      %if entry.end_entries:
    while (!${'should end' |variable})
      %else:
    while (buffer->num_bits > 0)
      %endif
    {
      %if contains_data(entry):
        i = result->count;
        ++result->count;
        %if child_contains_data(entry.children[0]):
        result->items = (${child_type}*)realloc(result->items, sizeof(${child_type}) * (result->count));
        %endif
      %endif
    %endif

      ## Check for the 'should end' happening early
      %if entry.end_entries:
        <% validate_end = '%s || ' % variable('should end') %>
    %else:
        <% validate_end = '' %>
      %endif

        if (${validate_end}!${settings.decode_name(entry.children[0].entry)}(buffer${settings.call_params(entry, 0, '&result->items[i]')}))
        {
      %if child_contains_data(entry.children[0]):
            unsigned int j;
            for (j=0; j< i; ++j)
            {
                ${settings.free_name(entry.children[0].entry)}(&result->items[j]);
            }
            free(result->items);
      %endif
            return 0;
        }
    }

      %if entry.end_entries:
    if (!${'should end'|variable})
    {
        // The data finished without receiving an 'end sequence'!
        %if contains_data(entry):
        ${settings.free_name(entry)}(result);
        %endif
        return 0;
    }
      %endif

</%def>

<%def name="decodeChoice(entry)">
    %if contains_data(entry):
    memset(result, 0, sizeof(${settings.ctype(entry)}));
    %endif
    BitBuffer temp;
    <% names = esc_names(('temp %s' % c.name for c in entry.children), variable) %>
    %for i, child in enumerate(entry.children):
      %if child_contains_data(child) and (is_recursive(entry, child.entry) or not contains_data(entry)):
    ${settings.ctype(child.entry)} ${names[i]};
      %endif
    %endfor
    %for i, child in enumerate(entry.children):
      %if is_recursive(entry, child.entry) or not contains_data(entry):
    <% temp_name = names[i] %>
      %else:
    <% temp_name = 'result->value.' + settings.var_name(entry, i) %>
      %endif
    <% if_ = "if" if i == 0 else 'else if' %>
    ${if_} (temp = *buffer, ${settings.decode_name(child.entry)}(&temp${settings.call_params(entry, i, "&%s" % temp_name)}))
    {
      %for name, temp in settings.option_output_temporaries(entry, i).items():
        %if name not in [local.name for local in local_vars(entry)]:
        *${name} = ${temp};
        %else:
        ${name} = ${temp};
        %endif
      %endfor
      %if contains_data(entry):
          %if settings.children_contain_data(entry):
        result->option = ${settings.enum_value(entry, i)};
          %else:
        *result = ${settings.enum_value(entry, i)};
          %endif
      %endif
        *buffer = temp;
      %if child_contains_data(child) and is_recursive(entry, child.entry):
        <% child_type = settings.ctype(child.entry) %>
        result->value.${settings.var_name(entry, i)} = (${child_type}*)malloc(sizeof(${child_type}));
        *result->value.${settings.var_name(entry, i)} = ${temp_name};
      %endif
    }
    %endfor
    else
    {
        /* Decode failed, no options succeeded... */
        return 0;
    }
</%def>

## Recursively create functions for decoding the entries contained within this protocol specification.
<%def name="recursiveDecode(entry, is_static=True)">
%for child in entry.children:
  %if child.entry not in common:
${recursiveDecode(child.entry)}
  %endif
%endfor

<% static = "static " if is_static else "" %>
%if contains_data(entry) or (isinstance(entry, Field) and entry.format != Field.INTEGER):
${static}void ${settings.free_name(entry)}(${settings.ctype(entry)}* value)
{
  %if isinstance(entry, Field):
    %if settings.is_numeric(settings.ctype(entry)):

    %elif entry.format == Field.TEXT:
    free(value->buffer);
    %elif entry.format == Field.HEX:
    free(value->buffer);
    %elif entry.format == Field.BINARY:
    free(value->buffer);
    %endif
  %elif isinstance(entry, Sequence):
    %for i, child in enumerate(entry.children):
        %if child_contains_data(child):
    ${settings.free_name(child.entry)}(&value->${settings.var_name(entry, i)});
        %endif
    %endfor
  %elif isinstance(entry, SequenceOf):
    %if child_contains_data(entry.children[0]):
    unsigned int i;
    for (i = 0; i < value->count; ++i)
    {
        ${settings.free_name(entry.children[0].entry)}(&value->items[i]);
    }
    free(value->items);
    %endif
  %elif isinstance(entry, Choice):
      %if settings.children_contain_data(entry):
    switch(value->option)
      %else:
    switch(*value)
      %endif
    {
    %for i, child in enumerate(entry.children):
    case ${enum_value(entry, i)}:
      %if child_contains_data(child):
        <% child_var = "value->value.%s" % settings.var_name(entry, i) %>
        %if not is_recursive(entry, child.entry):
          <% child_var = '&' + child_var %>
        %endif
        ${settings.free_name(child.entry)}(${child_var});
        %if is_recursive(entry, child.entry):
        free(${child_var});
        %endif
      %endif
        break;
    %endfor
    }
  %else:
    <% raise Exception("Don't know how to free objects of type '%s'" % entry) %>
  %endif
}
%endif


${static}int ${settings.decode_name(entry)}(BitBuffer* buffer${settings.define_params(entry)})
{
  %for local in settings.local_variables(entry):
    ${settings.ctype(local.type)} ${local.name};
  %endfor
  %if is_length_referenced(entry):
    unsigned int ${'initial length' |variable} = buffer->num_bits;
  %endif
  %if entry.length is not None:
    <% length = variable(entry.name + " expected length") %>
    unsigned int ${length} = ${settings.value(entry, entry.length)};
    unsigned int ${'unused number of bits' |variable} = buffer->num_bits - ${length};
    if (${length} > buffer->num_bits)
    {
        /* Not enough data */
        return 0;
    }
    buffer->num_bits = ${length};
  %endif
  %if isinstance(entry, Field):
    ${decodeField(entry)}
  %elif isinstance(entry, Sequence):
    ${decodeSequence(entry)}
  %elif isinstance(entry, SequenceOf):
    ${decodeSequenceOf(entry)}
  %elif isinstance(entry, Choice):
    ${decodeChoice(entry)}
  %endif
  %if is_end_sequenceof(entry):
    *${'should end' |variable} = 1;
  %endif
  %if entry.length is not None:
    if (buffer->num_bits != 0)
    {
        /* The entry didn't use all of the data */
      %if contains_data(entry):
        ${settings.free_name(entry)}(result);
      %endif
        return 0;
    }
    buffer->num_bits = ${'unused number of bits' |variable};
  %endif
  %if is_length_referenced(entry):
    *${entry.name + ' length' |variable} = ${'initial length' |variable} - buffer->num_bits;
  %endif
    return 1;
}
</%def>

${recursiveDecode(entry, False)}

<%def name="print_whitespace()">
    if (offset > 0)
    {
        printf("%*c", offset, ' ');
    }
</%def>


## Recursively create the function for printing the entries.
##
## We buffer the output, as the generated output will be filtered to adjust
## the whitespace offset.
<%def name="print_child(child, name, offset=2)" buffered="True">
   %if not is_hidden(child.name):
     %if contains_data(child.entry):
${settings.print_name(child.entry)}(${name}, offset + ${offset}, ${'"%s"' % xmlname(child.name)});
     %else:
${settings.print_name(child.entry)}(offset + ${offset}, ${'"%s"' % xmlname(child.name)});
     %endif
   %endif
</%def>

<%def name="recursivePrint(entry, is_static)" buffered="True">
%for child in entry.children:
  %if not is_hidden(entry.name) and not is_hidden(child.name) and  child.entry not in common:
${recursivePrint(child.entry, True)}
  %endif
%endfor

<% static = "static " if is_static else "" %>
%if contains_data(entry):
${static}void ${settings.print_name(entry)}(${settings.ctype(entry)}* data, unsigned int offset, const char* name)
%else:
${static}void ${settings.print_name(entry)}(unsigned int offset, const char* name)
%endif
{
  %if not entry.is_hidden():
    %if isinstance(entry, Field):
    ${print_whitespace()}
      %if not contains_data(entry):
    printf(${'"<%s />\\n"'}, name);
      %elif entry.format == Field.INTEGER:
    printf(${'"<%s>' + settings.printf_format(settings.ctype(entry)) + '</%s>\\n"'}, name, *data, name);
      %elif entry.format == Field.TEXT:
    printf(${'"<%s>"'}, name);
    print_escaped_string(data);
    printf(${'"</%s>\\n"'}, name);
      %elif entry.format == Field.HEX:
    printf(${'"<%s>"'}, name);
        <% iter_name = variable(entry.name + ' counter') %>
    unsigned int ${iter_name};
    for (${iter_name} = 0; ${iter_name} < data->length; ++${iter_name})
    {
        printf("%02x", data->buffer[${iter_name}]);
    }
    printf(${'"</%s>\\n"'}, name);
      %elif entry.format == Field.BINARY:
    printf(${'"<%s>"'}, name);
        <% copy_name = variable('copy of ' + entry.name) %>
        <% iter_name = variable(entry.name + ' whitespace counter') %>
        %if settings.is_numeric(settings.ctype(entry)):
          <% length = EntryLengthType(entry).range(raw_params).min %>
    BitBuffer ${copy_name} = {data, 8 - ${length}, ${length}};
        %else:
    BitBuffer ${copy_name} = *data;
        %endif
    unsigned int ${iter_name} = ${copy_name}.num_bits > 8 ? ${copy_name}.num_bits % 8 : 8;
    for (; ${copy_name}.num_bits != 0; --${iter_name})
    {
        if (${iter_name} == 0)
        {
            putchar(' ');
            ${iter_name} = 8;
        }
        printf("%u", decode_integer(&${copy_name}, 1));
    }
    printf(${'"</%s>\\n"'}, name);
      %elif entry.format == Field.FLOAT:
    printf(${'"<%s>%f</%s>\\n"'}, name, *data, name);
      %else:
    <% raise Exception("Don't know how to print %s" % entry) %>
      %endif
    %elif settings.is_numeric(settings.ctype(entry)):
    ${print_whitespace()}
      %if contains_data(entry):
    printf(${'"<%s>' + settings.printf_format(settings.ctype(entry)) + '</%s>\\n"'}, name, *data, name);
      %else:
    printf(${'"<%s />\\n"'}, name);
      %endif
    %elif isinstance(entry, Choice):
      %if settings.children_contain_data(entry):
    switch(data->option)
      %else:
    switch(*data)
      %endif
    {
      %for i, child in enumerate(entry.children):
    case ${enum_value(entry, i)}:
        %if not is_hidden(child.name):
          <% child_var = "data->value.%s" % (settings.var_name(entry, i)) %>
          %if not is_recursive(entry, child.entry):
            <% child_var = '&%s' % child_var %>
          %endif
        ${print_child(child, child_var, 0)|ws(8)}
        %endif
        break;
      %endfor
    }
    %elif isinstance(entry, Sequence):
    ${print_whitespace()}
    printf(${'"<%s>\\n"'}, name);
      %for i, child in enumerate(entry.children):
        %if not is_hidden(child.name):
    ${print_child(child, "&data->%s" % settings.var_name(entry, i))|ws(4)}
        %endif
      %endfor
      %if entry.value is not None and not entry.is_hidden():
    offset += 2;
    ${print_whitespace()}
    <% format = settings.printf_format(settings.ctype(EntryValueType(entry))) %>
    printf("%${format[1]}\n", data->value);
    offset -= 2;
      %endif
    ${print_whitespace()}
    printf(${'"</%s>\\n"'}, name);
    %elif isinstance(entry, SequenceOf):
    ${print_whitespace()}
    printf(${'"<%s>\\n"'}, name);
      %if not is_hidden(entry.children[0].name):
        <% iter_name = variable(entry.name + ' counter') %>
    unsigned int ${iter_name};
    for (${iter_name} = 0; ${iter_name} < data->count; ++${iter_name})
    {
        ${print_child(entry.children[0], '&data->items[%s]' % (iter_name))|ws(8)}
    }
      %endif
    ${print_whitespace()}
    printf(${'"</%s>\\n"'}, name);
    %else:
      <% raise Exception("Don't know how to print %s!" % entry) %>
    %endif
  %endif
}
</%def>

${recursivePrint(entry, False)}

<%def name="encodeField(entry)" buffered="True">
    <% value = settings.get_expected(entry) %>
    <% value_name = '*value' if value is None else 'value' %>
    %if value is not None:
    ${settings.ctype(entry)} value = ${value};
    %endif
    %if entry.format == Field.INTEGER:
      %if entry.encoding == Field.BIG_ENDIAN:
    encode_big_endian_integer(${value_name}, ${settings.value(entry, entry.length)}, result);
      %else:
    encode_little_endian_integer(${value_name}, ${settings.value(entry, entry.length)}, result);
      %endif
    %elif entry.format == Field.BINARY:
      %if settings.is_numeric(settings.ctype(entry)):
        <% length = EntryLengthType(entry).range(raw_params).min %>
    BitBuffer copy = {&${value_name}, 8 - ${length}, ${length}};
      %else:
    BitBuffer copy = ${value_name};
      %endif

    appendBuffer(result, &copy);
    %elif entry.format == Field.TEXT:
    appendText(result, value);
    %else:
      <% raise Exception("Don't know how to encode field %s!" % entry) %>
    %endif
</%def>

<%def name="encodeSequence(entry)" buffered="True">
    %for i, child in enumerate(entry.children):
      %if child_contains_data(child):
    if (!${settings.encode_name(child.entry)}(&value->${settings.var_name(entry, i)}, result))
      %else:
    if (!${settings.encode_name(child.entry)}(result))
      %endif
    {
        return 0;
    }
    %endfor
</%def>

<%def name="encodeChoice(entry)" buffered="True">
    <% option = 'value->option' if settings.children_contain_data(entry) else '*value' %>
    switch (${option})
    {
      %for i, child in enumerate(entry.children):
    case ${enum_value(entry, i)}:
        %if child_contains_data(child):
        return ${settings.encode_name(child.entry)}(&value->value.${settings.var_name(entry, i)}, result);
        %else:
        return ${settings.encode_name(child.entry)}(result);
        %endif
      %endfor
    default:
      return 0;
    }
</%def>

<%def name="encodeSequenceof(entry)" buffered="True">
    int i;
    for (i = 0; i < value->count; ++i)
    {
      %if child_contains_data(entry.children[0]):
        if (!${settings.encode_name(entry.children[0].entry)}(&value->items[i], result))
      %else:
        if (!${settings.encode_name(entry.children[0].entry)}(result))
      %endif
        {
            return 0;
        }
    }
</%def>

<%def name="recursiveEncode(entry, is_static)" buffered="True">
%for child in entry.children:
  %if child.entry not in common:
${recursiveEncode(child.entry, True)}
  %endif
%endfor

<% static = "static " if is_static else "" %>
%if contains_data(entry):
${static} int ${settings.encode_name(entry)}(${settings.ctype(entry)}* value, struct EncodedData* result)
%else:
${static} int ${settings.encode_name(entry)}(struct EncodedData* result)
%endif
{
  %if isinstance(entry, Field):
    ${encodeField(entry)}
  %elif isinstance(entry, Sequence):
    ${encodeSequence(entry)}
  %elif isinstance(entry, Choice):
    ${encodeChoice(entry)}
  %elif isinstance(entry, SequenceOf):
    ${encodeSequenceof(entry)}
  %else:
    <% raise Exception("Don't know how to encode entry %s!" % entry) %>
  %endif
    return 1;
}

</%def>

%if generate_encoder:
${recursiveEncode(entry, False)}
%endif
