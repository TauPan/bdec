## vim:set syntax=mako:
<%namespace file="/decodeentry.tmpl" name="decodeentry" />
<%namespace file="/expression.tmpl" name="expr" />
<%namespace file="/type.tmpl" name="ctype" />
<%! 
  from bdec.choice import Choice
  from bdec.field import Field
  from bdec.sequence import Sequence
  from bdec.sequenceof import SequenceOf
 %>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "${entry.name |filename}.h"
#include "buffer.h"
#include "variable_integer.h"

<%def name="success(entry)">
  %if is_length_referenced(entry):
    *${entry.name + ' length' |variable} = ${'initial length' |variable} - buffer->num_bits;
  %endif
    return 1;
</%def>

## Recursively create functions for decoding the entries contained within this protocol specification.
<%def name="recursiveDecode(entry)">
%for child in entry.children:
  %if child not in common:
${recursiveDecode(child)}
  %endif
%endfor

int ${ctype.decode_name(entry)}(BitBuffer* buffer, ${ctype.ctype(entry)}* result${decodeentry.define_params(entry)})
{
  %for local in local_vars(entry):
      int ${local} = 0;
  %endfor
  %if is_length_referenced(entry):
      int ${'initial length' |variable} = buffer->num_bits;
  %endif
  %if isinstance(entry, Field):
    ${decodeentry.decodeField(entry, "(*result)")}
    %if is_end_sequenceof(entry):
    *${'should end' |variable} = 1;
    %endif
    ${success(entry)}
  %elif isinstance(entry, Sequence):
    %for child in entry.children:
    if (!${ctype.decode_name(child)}(buffer, &result->${ctype.var_name(child, entry.children)}${decodeentry.params(entry, child)}))
    {
        return 0;
    }
    %endfor
    %if is_end_sequenceof(entry):
    *${'should end' |variable} = 1;
    %endif
    ${success(entry)}
  %elif isinstance(entry, SequenceOf):
    int i;
    %if entry.count is not None:
    result->count = ${expr.length(entry.count)};
    result->items = malloc(sizeof(${ctype.ctype(entry.children[0])}) * result->count);
    for (i = 0; i < result->count; ++i)
    {
    %else:
    result->items = 0;
    result->count = 0;
    while (!${'should end' |variable})
    {
        i = result->count;
        ++result->count;
        result->items = realloc(result->items, sizeof(${ctype.ctype(entry.children[0])}) * (result->count + 1));
    %endif
        if (!${ctype.decode_name(entry.children[0])}(buffer, &result->items[i]${decodeentry.params(entry, entry.children[0])}))
        {
            return 0;
        }
      %if is_end_sequenceof(entry):
      *${'should end' |variable} = 1;
      %endif
    }
    ${success(entry)}
  %elif isinstance(entry, Choice):
    memset(result, 0, sizeof(${ctype.ctype(entry)}));
    BitBuffer temp;
    %for child in entry.children:
    temp = *buffer;
    <% temp_name = variable('temp ' + esc_name(child, entry.children)) %>
    ${ctype.ctype(child)}* ${temp_name} = malloc(sizeof(${ctype.ctype(child)}));
    if (${ctype.decode_name(child)}(&temp, ${temp_name}${decodeentry.params(entry, child)}))
    {
        *buffer = temp;
        result->${ctype.var_name(child, entry.children)} = ${temp_name};
        ${success(entry)}
    }
    %endfor
    // Decode failed, no options succeeded...
    return 0;
  %endif
}
</%def>

${recursiveDecode(entry)}


## Recursively create functions for printing the entries contained within this protocol specification.
<%def name="recursivePrint(item, varname)">
  %if item in common and item is not entry:
    ${ctype.print_name(item)}(&${varname});
  %else:
    printf("<${item.name |xmlname}>\n");
    %if isinstance(item, Field):
      %if item.format == Field.INTEGER:
    printf("  %i\n", ${varname}); 
      %elif item.format == Field.TEXT:
    printf("  %s\n", ${varname});
      %elif item.format == Field.HEX:
        <% iter_name = variable(item.name + ' counter') %>
    int ${iter_name};
    printf("  ");
    for (${iter_name} = 0; ${iter_name} < ${varname}.length; ++${iter_name})
    {
        printf("%x", ${varname}.buffer[${iter_name}]);
    }
    printf("\n");
      %elif item.format == Field.BINARY:
        <% copy_name = variable('copy of ' + item.name) %>
        <% iter_name = variable(item.name + ' counter') %>
    BitBuffer ${copy_name} = ${varname};
    int ${iter_name};
    printf("  ");
    for (${iter_name} = 0; ${iter_name} < ${varname}.num_bits; ++${iter_name})
    {
        printf("%i", decode_integer(&${copy_name}, 1));
    }
    printf("\n");
      %else:
    #error Don't know how to print ${item}
      %endif
    %elif isinstance(item, Sequence):
      %for child in item.children:
    ${recursivePrint(child, '%s.%s' % (varname, variable(esc_name(child, item.children))))}
      %endfor
    %elif isinstance(item, SequenceOf):
      <% iter_name = variable(item.name + ' counter') %>
    int ${iter_name};
    for (${iter_name} = 0; ${iter_name} < ${varname}.count; ++${iter_name})
    {
        ${recursivePrint(item.children[0], '%s.items[%s]' % (varname, iter_name))}
    }
    %elif isinstance(item, Choice):
      %for child in item.children:
    if (${'%s.%s' % (varname, variable(esc_name(child, item.children)))} != 0)
    {
        ${recursivePrint(child, "(*%s.%s)" % (varname, variable(esc_name(child, item.children))))}
    }
      %endfor
    %else:
    #error Don't know how to print ${item}
    %endif
    printf("</${item.name |xmlname}>\n");
  %endif
</%def>

void ${ctype.print_name(entry)}(${ctype.ctype(entry)}* data)
{
${recursivePrint(entry, '(*data)')}
}
