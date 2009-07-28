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

"""
Library to generate source code in various languages for decoding specifications.
"""

import mako.lookup
import mako.template
import mako.runtime
import os
import os.path
import pkg_resources
import sys

import bdec.choice as chc
import bdec.entry as ent
import bdec.inspect.param as prm
import bdec.output.xmlout

class SettingsError(Exception):
    "An error raised when the settings file is incorrect."
    pass

_SETTINGS = "settings.py"

def is_template(filename):
    # We ignore all 'hidden' files, and the setting files, when looking for templates.
    return not filename.startswith('.') and not filename.endswith('.pyc') \
        and filename != _SETTINGS

_template_cache = {}
def _load_templates(language):
    """
    Load all file templates for a given specification.

    Returns a tuple containing (common file templates, entry specific templates),
    where every template is a tuple containing (name, mako template).
    """
    # We cache the results, as it sped up the tests by about 3x.
    if language in _template_cache:
        return _template_cache[language]

    common_templates  = []
    entry_templates = []
    template_dir = 'templates/' + language
    for filename in pkg_resources.resource_listdir('bdec', template_dir):
        if is_template(filename):
            text = pkg_resources.resource_string('bdec', '%s/%s' % (template_dir, filename))
            template = mako.template.Template(text, uri=filename)
            if 'source' in filename:
                entry_templates.append((filename, template))
            else:
                common_templates.append((filename, template))
    _template_cache[language] = (common_templates, entry_templates)
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


class _EntryInfo(prm.CompoundParameters):
    def __init__(self, utils, params):
        self._utils = utils
        prm.CompoundParameters.__init__(self, params)

    def _get_name_map(self, entry):
        """Map an unescaped name to an escaped 'local' name."""
        # It is possible that locals would escape to the same name as a
        # parameter (for example, references with constraints, see the 060
        # sequence with constraint xml regression test). To avoid this, we
        # escape parameter names and locals together.
        names = [param.name for param in prm.CompoundParameters.get_params(self, entry)]
        names.extend(local.name for local in prm.CompoundParameters.get_locals(self, entry))

        escaped = self._utils.esc_names(names, self._utils.variable_name)
        return dict(zip(names, escaped))

    def get_local_name(self, entry, name):
        """Map an unescaped name to the 'local' variable name.

        This may be stored as a local or a variable."""
        return self._get_name_map(entry)[name]

    def get_locals(self, entry):
        # We don't to have a local that has the same name as the parent, so we
        # escape the name with respect to the parameter names. We can get
        # similar names for references with constraints (see the 060 sequence
        # with constraint xml regression test).
        names = self._get_name_map(entry)
        for local in prm.CompoundParameters.get_locals(self, entry):
            yield prm.Local(names[local.name], local.type)

    def get_params(self, entry):
        names = self._get_name_map(entry)
        for param in prm.CompoundParameters.get_params(self, entry):
            yield prm.Param(names[param.name], param.direction, param.type)
            
    def get_passed_variables(self, entry, child):
        names = self._get_name_map(entry)
        for param in prm.CompoundParameters.get_passed_variables(self, entry, child):
            if param.name == 'unknown':
                name = param.name
            else:
                name = names[param.name]
            yield prm.Param(name, param.direction, param.type)


class _Settings:
    _REQUIRED_SETTINGS = ['keywords']

    @staticmethod
    def load(language, globals):
        path = 'templates/%s/settings.py' % language
        config_file = pkg_resources.resource_stream('bdec', path).read()
        code = compile(config_file, path, 'exec')
        eval(code, globals)
        settings = _Settings()
        for key in globals:
            setattr(settings, key, globals[key])

        for keyword in _Settings._REQUIRED_SETTINGS:
            try:
                getattr(settings, keyword)
            except AttributeError:
                raise SettingsError("'%s' must have a '%s' entry!" % (config_file, keyword))
        return settings

class _Utils:
    def __init__(self, common, settings):
        self._common = common
        self._entries = self._detect_entries()
        self._settings = settings

        self._reachable_entries = {}
        for entry in self._entries:
            reachable = set()
            self._update_reachable(entry, reachable)
            self._reachable_entries[entry] = reachable

    def _update_reachable(self, entry, reached):
        if entry in reached:
            return
        reached.add(entry)

        for child in entry.children:
            try:
                reached.update(self._reachable_entries[child.entry])
            except KeyError:
                self._update_reachable(child.entry, reached)

    def is_recursive(self, parent, child):
        "Is the parent entry reachable from the given child."
        return parent in self._reachable_entries[child]

    def _detect_recursive(self, parent, child, parents):
        pass

    def _detect_entries(self):
        """
        Return a list of all entries.
        """
        entries = []
        for entry in self._common:
            entries.extend(self.iter_inner_entries(entry))
        return entries

    def iter_inner_entries(self, entry):
        """
        Iterate over all non-common entries.
        
        Note that entry is also returned, even if it is a common entry.
        """
        for child in entry.children:
           if child.entry not in self._common:
              for sub_child in self.iter_inner_entries(child.entry):
                  yield sub_child
        yield entry

    def iter_entries(self):
        return self._entries

    def iter_required_common(self, entry):
        items = set()
        for child in entry.children:
            if child.entry in self._common:
                if not isinstance(entry, chc.Choice) or not self.is_recursive(entry, child.entry):
                    items.add(child.entry)
            else:
                for e in self.iter_required_common(child.entry):
                    items.add(e)
        result = list(items)
        result.sort(key=lambda a:a.name)
        return result

    def iter_optional_common(self, entry):
        for child in entry.children:
            if child.entry in self._common:
                if isinstance(entry, chc.Choice):
                    yield child.entry
            else:
                for entry in self.iter_optional_common(child.entry):
                    yield entry

    def esc_names(self, names, escape):
        """Return a list of unique escaped names.

        names -- The names to escape.
        escape -- A function to call to escape the name.
        return -- A list of unique names (of the same size as the input names).
        """
        names = list(names)
        result = []
        for name in names:
            name = self.esc_name(name)
            count = None
            while 1:
                if count is None:
                    escaped = escape(name)
                    count = 0
                else:
                    escaped = escape('%s %i' % (name, count))
                    count += 1
                if escaped not in result:
                    # We found a unique escaped name
                    result.append(escaped)
                    break
        assert len(result) == len(names)
        return result

    def esc_name(self, name):
        """Escape a name so it doesn't include invalid characters."""
        if not name:
            return "_hidden"
        result = "".join(char for char in name if char in _VALID_CHARS)
        if result[0] in _NUMBERS:
            result = '_' + result
        return result

    def _check_keywords(self, name):
        if name in self._settings.keywords:
            return '%s_' % name
        return name

    def _camelcase(self, name):
        words = self.esc_name(name).split()
        result = "".join(word[0].upper() + word[1:].lower() for word in words)
        return self._check_keywords(result)

    def _delimiter(self, name, delim):
        words = self.esc_name(name).split()
        result = delim.join(words)
        return self._check_keywords(result)

    def variable_name(self, name):
        name = self._delimiter(name, ' ')
        return name[0].lower() + self._camelcase(name)[1:]

    def filename(self, name):
        basename, extension = os.path.splitext(name)
        return self._delimiter(basename, '').lower() + extension

    def type_name(self, name):
        result= self._camelcase(name)
        return result

    def constant_name(self, name):
        return self._delimiter(name, '_').upper()

def _crange(start, end):
    return [chr(i) for i in range(ord(start), ord(end)+1)]
_NUMBERS = _crange('0', '9')
_VALID_CHARS = _NUMBERS + _crange('a', 'z') + _crange('A', 'Z') + ['_', ' ']


def _whitespace(offset):
    """Create a filter for adding leading whitespace"""
    def filter(text):
        if not text:
            return text

        result = ""
        for line in text.splitlines(True):
            result += ' ' * offset + line
        return result
    return filter

def generate_code(spec, language, output_dir, common_entries=[]):
    """
    Generate code to decode the given specification.
    """
    common_templates, entry_templates = _load_templates(language)
    entries = set(common_entries)
    entries.add(spec)
    
    # We want the entries to be in a consistent order, otherwise the name
    # escaping might choose different names for the same entry across multiple
    # runs.
    entries = list(entries)
    entries.sort(key=lambda a:a.name)

    lookup = {}
    data_checker = prm.DataChecker(entries)
    lookup['settings'] = _Settings.load(language, lookup)
    utils = _Utils(entries, lookup['settings'])

    params = prm.CompoundParameters([
        prm.ResultParameters(entries),
        prm.ExpressionParameters(entries),
        prm.EndEntryParameters(entries),
        ])
    info = _EntryInfo(utils, [params])

    lookup['protocol'] = spec
    lookup['common'] = entries
    lookup['esc_name'] = utils.esc_name
    lookup['esc_names'] = utils.esc_names
    lookup['get_params'] = info.get_params
    lookup['raw_params'] = params
    lookup['get_passed_variables'] = info.get_passed_variables
    lookup['is_end_sequenceof'] = info.is_end_sequenceof
    lookup['is_hidden'] = ent.is_hidden
    lookup['is_value_referenced'] = info.is_value_referenced
    lookup['is_length_referenced'] = info.is_length_referenced
    lookup['is_recursive'] = utils.is_recursive
    lookup['child_contains_data'] = data_checker.child_has_data
    lookup['contains_data'] = data_checker.contains_data
    lookup['iter_inner_entries'] = utils.iter_inner_entries
    lookup['iter_required_common'] = utils.iter_required_common
    lookup['iter_optional_common'] = utils.iter_optional_common
    lookup['iter_entries'] = utils.iter_entries
    lookup['local_vars'] = info.get_locals
    lookup['local_name'] = info.get_local_name
    lookup['constant'] = utils.constant_name
    lookup['filename'] = utils.filename
    lookup['function'] = utils.variable_name
    lookup['typename'] = utils.type_name
    lookup['variable'] = utils.variable_name
    lookup['ws'] = _whitespace
    lookup['xmlname'] = bdec.output.xmlout.escape_name

    for filename, template in common_templates:
        _generate_template(output_dir, filename, lookup, template)
    for filename, template in entry_templates:
        for entry in entries:
            lookup['entry'] = entry
            _generate_template(output_dir, utils.filename(filename.replace('source', entry.name)), lookup, template)

