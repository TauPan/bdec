# Copyright (c) 2010, PRESENSE Technologies GmbH
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the PRESENSE Technologies GmbH nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from bdec.encode.choice import ChoiceEncoder
from bdec.encode.entry import Child, is_hidden
from bdec.encode.field import FieldEncoder
from bdec.encode.sequence import SequenceEncoder
from bdec.encode.sequenceof import SequenceOfEncoder
from bdec.choice import Choice
from bdec.field import Field
from bdec.inspect.param import ExpressionParameters
from bdec.inspect.type import EntryLengthType, EntryValueType, MultiSourceType
from bdec.sequence import Sequence
from bdec.sequenceof import SequenceOf

_encoders = {
        Choice : ChoiceEncoder,
        Field : FieldEncoder,
        Sequence : SequenceEncoder,
        SequenceOf : SequenceOfEncoder,
        }

class EncodeParams:
    def __init__(self, entry):
        self._hidden_map = {}
        common = set()
        self._detect_common(entry, entry.name, common)
        self._populate_visible(entry, common, self._hidden_map)
        self.expression_params = ExpressionParameters([entry])

    def is_hidden(self, entry):
        return self._hidden_map[entry]

    def is_length_referenced(self, entry):
        return self.expression_params.is_length_referenced(entry)

    def is_value_referenced(self, entry):
        return self.expression_params.is_value_referenced(entry)

    def get_params(self, entry):
        print 'asked for params for %s' % entry
        result = self._params(self.expression_params.get_params(entry),
                self._hidden_map[entry])
        print '   %s' % result
        return result

    def get_passed_variables(self, entry, child):
        is_child_hidden = self.is_hidden(child.entry) or is_hidden(child.name)
        print 'asked for params passed from %s to %s' % (entry, child)
        result = self._params(self.expression_params.get_passed_variables(entry, child),
                is_child_hidden)
        print '   %s' % result
        return result

    def _detect_common(self, entry, name, common, visited=None):
        """Detect any common entries.

        Common entries are those that have renamed names, or are referenced in
        multiple locations."""
        if visited is None:
            visited = set()
        if entry in visited or entry.name != name:
            common.add(entry)
            return
        visited.add(entry)
        for child in entry.children:
            self._detect_common(child.entry, child.name, common, visited)

    def _populate_visible(self, entry, common, entries, visible=True):
        if entry in entries:
            return

        if entry in common:
            # Common entries are visible if their name is public, regardless of
            # what their parents do.
            visible = not is_hidden(entry.name)
        else:
            # Entries that aren't common are visible if both they and their parents
            # are visible.
            visible &= not is_hidden(entry.name)

        entries[entry] = not visible
        for child in entry.children:
            self._populate_visible(child.entry, common, entries, visible)

    def _is_source_entry_independant(self, param_type, is_value_hidden):
        """Test if the source entry be encoded without knowledge of how its reference is used.

        For example, if the source entry is visible, or has an expected value, it
        can be encoded without knowledge of how the reference is used. If the
        source entry is hidden, and its value used in a visible entry (for example,
        in the count of a sequence-of), the source entry must be encoded after the
        user of its reference so the value can be detected."""
        if param_type.has_expected_value() or isinstance(param_type, EntryLengthType):
            result = True
        elif isinstance(param_type, EntryValueType):
            # If we reference an entry value, the source is independant if it is
            # visible.
            if is_value_hidden:
                return False
            result = not self._hidden_map[param_type.entry]
        elif isinstance(param_type, MultiSourceType):
            for source in param_type.sources:
                if not _is_source_entry_independant(source, is_value_hidden):
                    result = False
                    break
            else:
                result = True
        else:
            raise NotImplementedError('Unknown param type when testing for independance')
        return result


    def _params(self, params, is_entry_hidden):
        """Change the order of the parameters such that they are suitable for encoding."""
        params = list(params)
        result = []
        for p in params:
            is_value_hidden = ':' in p.name or (p.direction == p.OUT and is_entry_hidden)
            if self._is_source_entry_independant(p.type, is_value_hidden):
                # The source entry is indepent of the user of it; no need to swap
                # the parameters.
                result.append(p)
            else:
                if p.direction == p.IN:
                    p.direction = p.OUT
                else:
                    p.direction = p.IN
                result.append(p)
        return result


def _get_encoder(entry, params, entries):
    try:
        encoder = entries[entry]
    except KeyError:
        # We haven't created an encoder for this entry yet.
        encoder = _encoders[type(entry)](entry, params.expression_params, params.get_params(entry), params.is_hidden(entry))
        entries[entry] = encoder

        for child in entry.children:
            is_child_hidden = params.is_hidden(child.entry) or is_hidden(child.name)
            encoder.children.append(Child(child.name,
                _get_encoder(child.entry, params, entries),
                params.get_passed_variables(entry, child), is_child_hidden))
    return encoder



def create_encoder(entry):
    params = EncodeParams(entry)
    return _get_encoder(entry, params, {})

