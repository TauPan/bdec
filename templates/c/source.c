## vim:set syntax=mako:

<%! 
  from bdec.choice import Choice
  from bdec.data import Data
  from bdec.field import Field
  from bdec.sequence import Sequence
  from bdec.sequenceof import SequenceOf
 %>

/*  Copyright (C) 2008 Henry Ludemann

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
  %if len(entry.expected) < 32:
    if (get_integer(&actual) != ${int(entry.expected)})
  %else:
    BitBuffer expected = {(unsigned char*)${settings.c_string(expected.bytes())}, 0, ${len(entry.expected)}};
    int isMatch = 1;
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

<%def name="decodeField(entry)">
    ${settings.ctype(entry)} value;
  %if entry.min is not None or entry.max is not None:
    BitBuffer field_data = *buffer;
    field_data.num_bits = ${settings.value(entry.length)};
  %endif
  %if entry.format == Field.INTEGER:
    %if entry.encoding == Field.BIG_ENDIAN:
    value = decode_integer(buffer, ${settings.value(entry.length)});
    %else:
    value = decode_little_endian_integer(buffer, ${settings.value(entry.length)});
    %endif
    %if is_value_referenced(entry):
    *${entry.name |variable} = value;
    %endif
  %elif entry.format == Field.TEXT:
    int i;
    int ${entry.name + ' buffer length' |variable} = ${settings.value(entry.length)} / 8;
    value = malloc(${entry.name + ' buffer length' |variable} + 1);
    value[${entry.name + ' buffer length' |variable}] = 0;
    for (i = 0; i < ${entry.name + ' buffer length' |variable}; ++i)
    {
        value[i] = decode_integer(buffer, 8);
    }
  %elif entry.format == Field.HEX:
    int i;
    assert((${settings.value(entry.length)}) % 8 == 0);
    value.length = ${settings.value(entry.length)} / 8;
    value.buffer = malloc(value.length);
    for (i = 0; i < value.length; ++i)
    {
        value.buffer[i] = decode_integer(buffer, 8);
    }
  %elif entry.format == Field.BINARY:
    value.start_bit = buffer->start_bit;
    value.num_bits = ${settings.value(entry.length)};
    // 0 bits = 0 bytes, 1-8 bits = 1 byte, 9-16 bytes = 2 bytes...
    int numBytes = (buffer->start_bit + buffer->num_bits + 7) / 8;
    value.buffer = malloc(numBytes);
    memcpy(value.buffer, buffer->buffer, numBytes);
    buffer->start_bit += value.num_bits;
    buffer->buffer += buffer->start_bit / 8;
    buffer->start_bit %= 8;
    buffer->num_bits -= value.num_bits;
  %else:
    #error Unknown field type ${entry}
  %endif
     %if entry.expected is not None:
       %if entry.format == entry.INTEGER:
    if (value != ${int(entry.expected)})
       %elif entry.format == entry.BINARY:
           <% 
           extra_bits = 8 - len(entry.expected) % 8
           expected = entry.expected + Data('\x00', start=0, end=extra_bits)
           %>
    BitBuffer actual = value;
    ${compare_binary_expected(entry, expected)}
       %elif entry.format == entry.HEX:
    BitBuffer actual = {value.buffer, 0, value.length * 8};
    ${compare_binary_expected(entry, entry.expected)}
       %elif entry.format == entry.TEXT:
    if (memcmp(value, ${settings.c_string(entry.expected.bytes())}, ${len(entry.expected) / 8}) != 0)
       %else:
#error Field of type ${entry.format} not currently supported for an expected value!
       %endif
    {
      %if entry.format != Field.INTEGER:
        ${settings.free_name(entry)}(&value);
      %endif
        return 0;
    }
     %endif
    %if entry.min is not None:
    if (get_integer(&field_data) < ${settings.value(entry.min)})
    {
      %if entry.format != Field.INTEGER:
        ${settings.free_name(entry)}(&value);
      %endif
        return 0;
    }
    %endif
    %if entry.max is not None:
    if (get_integer(&field_data) > ${settings.value(entry.max)})
    {
      %if entry.format != Field.INTEGER:
        ${settings.free_name(entry)}(&value);
      %endif
        return 0;
    }
    %endif
    %if not entry.is_hidden():
    (*result) = value;
    %else:
      %if entry.format == Field.TEXT:
    ${settings.free_name(entry)}(&value);
      %elif entry.format == Field.BINARY:
    ${settings.free_name(entry)}(&value);
      %elif entry.format == Field.HEX:
    ${settings.free_name(entry)}(&value);
      %endif
    %endif
</%def>

<%def name="decodeSequence(entry)">
    %for i, child in enumerate(entry.children):
    if (!${settings.decode_name(child.entry)}(buffer${settings.params(entry, i, '&result->%s' % variable(esc_name(i, entry.children)))}))
    {
        %for j, previous in enumerate(entry.children[:i]):
            %if contains_data(previous.entry):
        ${settings.free_name(previous.entry)}(&result->${settings.var_name(j, entry.children)});
            %endif
        %endfor
        return 0;
    }
    %endfor
    %if entry.value is not None:
    int value = ${settings.value(entry.value)};
      %if contains_data(entry):
    result->value = value;
      %endif
      %if is_value_referenced(entry):
    *${entry.name |variable} = value;
      %endif
    %endif
</%def>

<%def name="decodeSequenceOf(entry)">
    %if entry.count is not None:
    int i;
    int num_items;
    num_items = ${settings.value(entry.count)};
      %if contains_data(entry):
    result->count = num_items;
    result->items = malloc(sizeof(${settings.ctype(entry.children[0].entry)}) * result->count);
      %endif
    for (i = 0; i < num_items; ++i)
    {
    %else:
      %if contains_data(entry):
    int i;
    result->items = 0;
    result->count = 0;
      %endif
      %if entry.length is not None:
    while (buffer->num_bits > 0)
      %else:
    while (!${'should end' |variable})
      %endif
    {
      %if contains_data(entry):
        i = result->count;
        ++result->count;
        result->items = realloc(result->items, sizeof(${settings.ctype(entry.children[0].entry)}) * (result->count));
      %endif
    %endif
        if (!${settings.decode_name(entry.children[0].entry)}(buffer${settings.params(entry, 0, '&result->items[i]')}))
        {
      %if contains_data(entry):
            int j;
            for (j=0; j< i; ++j)
            {
                ${settings.free_name(entry.children[0].entry)}(&result->items[j]);
            }
            free(result->items);
      %endif
            return 0;
        }
    }

</%def>

<%def name="decodeChoice(entry)">
    %if contains_data(entry):
    memset(result, 0, sizeof(${settings.ctype(entry)}));
    %endif
    BitBuffer temp;
    %for i, child in enumerate(entry.children):
      %if contains_data(child.entry):
    <% temp_name = variable('temp ' + esc_name(i, entry.children)) %>
    ${settings.ctype(child.entry)} ${temp_name};
      %endif
    %endfor
    %for i, child in enumerate(entry.children):
    <% temp_name = variable('temp ' + esc_name(i, entry.children)) %>
    <% if_ = "if" if i == 0 else 'else if' %>
    ${if_} (temp = *buffer, ${settings.decode_name(child.entry)}(&temp${params(entry, i, "&%s" % temp_name)}))
    {
        *buffer = temp;
      %if contains_data(child.entry):
        result->${settings.var_name(i, entry.children)} = malloc(sizeof(${settings.ctype(child.entry)}));
        *result->${settings.var_name(i, entry.children)} = ${temp_name};
      %endif
    }
    %endfor
    else
    {
        // Decode failed, no options succeeded...
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
    %if entry.format == Field.TEXT:
    free(*value);
    %elif entry.format == Field.HEX:
    free(value->buffer);
    %elif entry.format == Field.BINARY:
    free(value->buffer);
    %endif
  %elif isinstance(entry, Sequence):
    %for i, child in enumerate(entry.children):
        %if contains_data(child.entry):
    ${settings.free_name(child.entry)}(&value->${settings.var_name(i, entry.children)});
        %endif
    %endfor
  %elif isinstance(entry, SequenceOf):
    int i;
    for (i = 0; i < value->count; ++i)
    {
        ${settings.free_name(entry.children[0].entry)}(&value->items[i]);
    }
    free(value->items);
  %elif isinstance(entry, Choice):
    %for i, child in enumerate(entry.children):
      %if contains_data(child.entry):
    if (value->${settings.var_name(i, entry.children)} != 0)
    {
        ${settings.free_name(child.entry)}(value->${settings.var_name(i, entry.children)});
        free(value->${settings.var_name(i, entry.children)});
    }
      %endif
    %endfor
  %else:
    <% raise Exception("Don't know how to free objects of type '%s'" % entry) %>
  %endif
}
%endif


${static}int ${settings.decode_name(entry)}(BitBuffer* buffer${settings.define_params(entry)})
{
  %for local in local_vars(entry):
    int ${local} = 0;
  %endfor
  %if is_length_referenced(entry):
    int ${'initial length' |variable} = buffer->num_bits;
  %endif
  %if entry.length is not None:
    <% length = variable(entry.name + " expected length") %>
    int ${length} = ${settings.value(entry.length)};
    int ${'unused number of bits' |variable} = buffer->num_bits - ${length};
    if (${length} > buffer->num_bits)
    {
        // Not enough data
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
        // The entry didn't use all of the data
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

<%def name="printText(text, value, ws_offset)">
  %if ws_offset == 0:
    ## We have to print in two runs, as we cannot print zero space characters 
    ## in a single print statement.
    if (offset + ${ws_offset} > 0)
    {
        printf("%*c", offset + ${ws_offset}, ' ');
    }
    %if value.startswith('"'):
    printf("${text % value[1:-1]}");
    %else:
    printf("${text}", ${value});
    %endif
  %else:
    %if value.startswith('"'):
    printf("%*c${text % value[1:-1]}", offset + ${ws_offset}, ' ');
    %else:
    printf("%*c${text}", offset + ${ws_offset}, ' ', ${value});
    %endif
  %endif
</%def>

## Recursively create the function for printing the entries.
##
## We buffer the output, as the generated output will be filtered to adjust
## the whitespace offset.
<%def name="recursivePrint(item, name, varname, ws_offset, iter_postfix)" buffered="True">
  %if item in common and item is not entry:
    %if contains_data(item):
    ${settings.print_name(item)}(&${varname}, offset + ${ws_offset}, name);
    %endif
  %elif contains_data(item):
    %if isinstance(item, Field):
      %if not item.is_hidden():
    ${printText("<%s>", name , ws_offset)}
        %if item.format == Field.INTEGER:
    printf("%i", ${varname}); 
        %elif item.format == Field.TEXT:
    printf("%s", ${varname});
        %elif item.format == Field.HEX:
        <% iter_name = variable(item.name + ' counter' + str(iter_postfix.next())) %>
    int ${iter_name};
    for (${iter_name} = 0; ${iter_name} < ${varname}.length; ++${iter_name})
    {
        printf("%x", ${varname}.buffer[${iter_name}]);
    }
        %elif item.format == Field.BINARY:
        <% copy_name = variable('copy of ' + item.name + str(iter_postfix.next())) %>
        <% iter_name = variable(item.name + ' counter' + str(iter_postfix.next())) %>
    BitBuffer ${copy_name} = ${varname};
    int ${iter_name};
    for (${iter_name} = 0; ${iter_name} < ${varname}.num_bits; ++${iter_name})
    {
        printf("%i", decode_integer(&${copy_name}, 1));
    }
        %else:
    #error Don't know how to print ${item}
        %endif
      %endif
    %else:
    ## Print everything other than fields
      %if not item.is_hidden():
    ${printText("<%s>\\n", name, ws_offset)}
      %endif
      <% next_offset = (ws_offset + 4) if not item.is_hidden() else ws_offset %>
      %if isinstance(item, Sequence):
        %for i, child in enumerate(item.children):
${recursivePrint(child.entry, '"%s"' % xmlname(child.name), '%s.%s' % (varname, variable(esc_name(i, item.children))), next_offset, iter_postfix)}
        %endfor
        %if item.value is not None and not item.is_hidden():
    printf("%*i\n", offset + ${ws_offset+4}, ${varname}.value); 
        %endif
      %elif isinstance(item, SequenceOf):
        <% iter_name = variable(item.name + ' counter' + str(iter_postfix.next())) %>
    int ${iter_name};
    for (${iter_name} = 0; ${iter_name} < ${varname}.count; ++${iter_name})
    {
${recursivePrint(item.children[0].entry, '"%s"' % xmlname(item.children[0].name), '%s.items[%s]' % (varname, iter_name), next_offset, iter_postfix) | ws(4)}
    }
      %elif isinstance(item, Choice):
        %for i, child in enumerate(item.children):
          %if contains_data(child.entry):
    if (${'%s.%s' % (varname, variable(esc_name(i, item.children)))} != 0)
    {
${recursivePrint(child.entry, '"%s"' % xmlname(child.name), "(*%s.%s)" % (varname, variable(esc_name(i, item.children))), next_offset, iter_postfix) | ws(4)}
    }
          %endif
        %endfor
      %else:
    #error Don't know how to print ${item}
      %endif
    %endif
    %if not item.is_hidden():
      %if not isinstance(item, Field):
    ${printText("</%s>\\n", name, ws_offset)}
      %elif name.startswith('"'):
    printf("</${name[1:-1]}>\n");
      %else:
    printf("</${'%s'}>\n", ${name});
      %endif
    %endif
  %endif
</%def>

void ${settings.print_name(entry)}(${settings.ctype(entry)}* data, int offset, char* name)
{
${recursivePrint(entry, 'name', '(*data)', 0, iter(xrange(100)))}
}

