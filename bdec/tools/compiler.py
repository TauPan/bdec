"""
Library to generate source code in various languages for decoding specifications.
"""

import mako.lookup
import mako.template
import mako.runtime
import os
import os.path
import sys

import bdec.inspect.param as prm
import bdec.output.xmlout

_template_cache = {}
def _load_templates(directory):
    """
    Load all file templates for a given specification.

    Returns a tuple containing (common file templates, entry specific templates),
    where every template is a tuple containing (name, mako template).
    """
    # We cache the results, as it sped up the tests by about 3x.
    if directory in _template_cache:
        return _template_cache[directory]

    common_templates  = []
    entry_templates = []
    for filename in os.listdir(directory):
        if not filename.endswith('.tmpl') and not filename.startswith('.'):
            path = os.path.join(directory, filename)
            lookup = mako.lookup.TemplateLookup(directories=[directory])
            template = mako.template.Template(filename=path, lookup=lookup)
            if 'source' in filename:
                entry_templates.append((filename, template))
            else:
                common_templates.append((filename, template))
    _template_cache[directory] = (common_templates, entry_templates)
    return (common_templates, entry_templates)

def _generate_template(output_dir, filename, lookup, template):
    output = file(os.path.join(output_dir, filename), 'w')
    try:
        context = mako.runtime.Context(output, **lookup)
        template.render_context(context)
    except:
        raise Exception(mako.exceptions.text_error_template().render())
    finally:
        output.close()

def _recursive_update(common_references, common, entry):
    if entry in common:
        common_references.add(entry)
    else:
        for child in entry.children:
            _recursive_update(common_references, common, child)


class _EntryInfo(prm.ParamLookup):
    def get_locals(self, entry):
        for local in prm.ParamLookup.get_locals(self, entry):
            yield _variable_name(local)

    def get_params(self, entry):
        for param in prm.ParamLookup.get_params(self, entry):
            yield prm.Param(_variable_name(param.name), param.direction)
            
    def get_invoked_params(self, entry, child):
        for param in prm.ParamLookup.get_invoked_params(self, entry, child):
            yield prm.Param(_variable_name(param.name), param.direction)

def _create_iter_inner_entries(common):
    """
    Create a function that can iterate over all non-common entries.
    
    Note that entry is also returned, even if it is a common entry.
    """
    def iter_inner_entries(entry):
        for child in entry.children:
           if child not in common:
              for sub_child in iter_inner_entries(child):
                  yield sub_child
        yield entry
    return iter_inner_entries

def _create_iter_entries(common):
    """Create a function that returns an iterator to all the entries."""
    iter_inner_entries = _create_iter_inner_entries(common)
    entries = []
    for entry in common:
        entries.extend(iter_inner_entries(entry))
    def iter_entries():
        return entries
    return iter_entries

def _esc_name(entry, iter_entries):
    lookup = {}
    for e in iter_entries:
        lookup.setdefault(e.name, []).append(e)
    names = {}
    for name, entries in lookup.iteritems():
        if len(entries) == 1:
            names[entries[0]] = name
        else:
            names.update((e, "%s %i" % (name, i)) for i, e in enumerate(entries))
    try:
        return names[entry]
    except KeyError:
        raise Exception("Entry '%s' name to escape must be in group (%s)!" % (entry, iter_entries))

def _crange(start, end):
    return [chr(i) for i in range(ord(start), ord(end))] 
_VALID_CHARS = _crange('0', '9') + _crange('a', 'z') + _crange('A', 'Z') + ['_', ' ']

def _escape_name(name):
    return "".join(char for char in name if char in _VALID_CHARS)

def _camelcase(name):
    words = _escape_name(name).split()
    return "".join(word[0].upper() + word[1:].lower() for word in words)

def _delimiter(name, delim):
    words = _escape_name(name).split()
    return delim.join(words)

def _variable_name(name):
    name = _delimiter(name, ' ')
    return name[0].lower() + _camelcase(name)[1:]

def _filename(name):
    basename, extension = os.path.splitext(name)
    return _delimiter(basename, '').lower() + extension

def _type_name(name):
    result= _camelcase(name)
    return result

def _constant_name(name):
    return _delimiter(name, '_').upper()

def generate_code(spec, template_path, output_dir, common_entries=[]):
    """
    Generate code to decode the given specification.
    """
    common_templates, entry_templates = _load_templates(template_path)

    lookup = {}
    for filename, template in common_templates:
        _generate_template(output_dir, filename, lookup, template)
    entries = set(common_entries)
    entries.add(spec)
    info = _EntryInfo(entries)
    for filename, template in entry_templates:
        for entry in entries:
            referenced_entries = set()
            common_items = entries.copy()
            common_items.remove(entry)
            _recursive_update(referenced_entries, common_items, entry)

            lookup['entry'] = entry
            lookup['esc_name'] = _esc_name
            lookup['common'] = referenced_entries
            lookup['get_params'] = info.get_params
            lookup['get_invoked_params'] = info.get_invoked_params
            lookup['is_end_sequenceof'] = info.is_end_sequenceof
            lookup['is_value_referenced'] = info.is_value_referenced
            lookup['is_length_referenced'] = info.is_length_referenced
            lookup['iter_inner_entries'] = _create_iter_inner_entries(entries)
            lookup['iter_entries'] = _create_iter_entries(entries)
            lookup['local_vars'] = info.get_locals
            lookup['constant'] = _constant_name
            lookup['filename'] = _filename
            lookup['function'] = _variable_name
            lookup['typename'] = _type_name
            lookup['variable'] = _variable_name
            lookup['xmlname'] = bdec.output.xmlout.escape_name
            _generate_template(output_dir, _filename(filename.replace('source', entry.name)), lookup, template)

