
import bdec
import bdec.choice as chc
import bdec.entry as ent
import bdec.field as fld
import bdec.sequence as seq
import bdec.sequenceof as sof
import bdec.spec.expression as expr


class BadReferenceError(bdec.DecodeError):
    def __init__(self, entry, name):
        bdec.DecodeError.__init__(self, entry)
        self.name = name

    def __str__(self):
        return "Cannot reference '%s' in %s" % (self.name, self.entry)

class BadReferenceTypeError(bdec.DecodeError):
    def __init__(self, entry):
        bdec.DecodeError.__init__(self, referenced)

    def __str__(self):
        return "Cannot reference non integer field '%s'" % self.entry

class Param(object):
    """Class to represent parameters passed into and out of decodes. """
    IN = "in"
    OUT = "out"

    def __init__(self, name, direction, type):
        self.name = name
        self.direction = direction
        self.type = type

    def __eq__(self, other):
        return self.name == other.name and self.direction == other.direction \
                and self.type == other.type

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return "%s %s '%s'" % (self.type, self.direction, self.name)


class _Parameters:
    """Interface for querying information about passed parameters"""
    def get_locals(self, entry):
        raise NotImplementedError()

    def get_params(self, entry):
        raise NotImplementedError()

    def get_passed_variables(self, entry, child):
        raise NotImplementedError()

    def is_end_sequenceof(self, entry):
        return False

    def is_value_referenced(self, entry):
        return False

    def is_length_referenced(self, entry):
        return False


class EndEntryParameters(_Parameters):
    """
    Class to allow querying of parameters used when decoding a sequence of.
    """
    def __init__(self, entries):
        self._has_context_lookup = {}

        self._end_sequenceof_entries = set()
        for entry in entries:
            self._populate_lookup(entry, [])

    def _populate_lookup(self, entry, intermediaries):
        if entry in self._has_context_lookup:
            return
        self._has_context_lookup.setdefault(entry, False)

        if isinstance(entry, sof.SequenceOf):
            self._end_sequenceof_entries.update(entry.end_entries)
            intermediaries = []
        else:
            intermediaries.append(entry)

        if entry in self._end_sequenceof_entries:
            # We found a 'end-sequenceof' entry. All the items between the end
            # entry and the sequenceof must be able to pass the 'end' context
            # back up to the sequenceof.
            for intermediary in intermediaries:
                self._has_context_lookup[intermediary] = True

        # Keep walking down the chain look for 'end-sequenceof' entries.
        for child in entry.children:
            self._populate_lookup(child, intermediaries[:])

    def _walk(self, entry, visited, offset):
        if entry in visited:
            return
        visited.add(entry)
        for child in children:
            self._walk(child, visited, offset + 1)

    def get_locals(self, entry):
        result = []
        if isinstance(entry, sof.SequenceOf):
            if entry.end_entries:
                result.append('should end')
        return result

    def get_params(self, entry):
        """
        If an item is between a sequenceof and an end-sequenceof entry, it
        should pass an output 'should_end' context item.
        """
        if self._has_context_lookup[entry]:
            return set([Param('should end', Param.OUT,  int)])
        return set()

    def get_passed_variables(self, entry, child):
        # The passed parameter names don't change for 'should end' variables;
        # the name is the same in both parent & child.
        return self.get_params(child)

    def is_end_sequenceof(self, entry):
        return entry in self._end_sequenceof_entries

class _VariableParam:
    def __init__(self, reference, direction):
        assert isinstance(reference, expr.ValueResult) or isinstance(reference, expr.LengthResult)
        self.reference = reference
        self.direction = direction

    def __hash__(self):
        return hash(self.reference.name)

    def __eq__(self, other):
        return self.reference.name == other.reference.name and self.direction == other.direction


class ExpressionParamters(_Parameters):
    """
    A class to calculate parameters passed between entries.

    All entries that have expressions can reference other entries; this class
    is responsible for detecting the parameters that must be passed between
    those entries to supply the data the expression requires.
    """
    def __init__(self, entries):
        self._params = {}
        self._locals = {}

        self._referenced_values = set()
        self._referenced_lengths = set()
        unreferenced_entries = {}
        for entry in entries:
            self._populate_references(entry, unreferenced_entries)
        self._detect_out_params()

    def _collect_references(self, expression):
        """
        Walk an expression object, collecting all named references.
        
        Returns a list of tuples of (entry instances, variable name).
        """
        result = []
        if isinstance(expression, expr.Constant):
            pass
        elif isinstance(expression, expr.ValueResult):
            result.append(expression)
        elif isinstance(expression, expr.LengthResult):
            result.append(expression)
        elif isinstance(expression, expr.Delayed):
            result = self._collect_references(expression.left) + self._collect_references(expression.right)
        else:
            raise Exception("Unable to collect references from unhandled expression type '%s'!" % expression)
        return result

    def _populate_references(self, entry, unreferenced_entries):
        """
        Walk down the tree, populating the '_params', '_referenced_XXX' sets.

        Handles recursive elements.
        """
        if entry in self._params:
            return
        self._params[entry] = set()
        unreferenced_entries[entry] = set()

        for child in entry.children:
            self._populate_references(child, unreferenced_entries)

        # An entries unknown references are those referenced in any 
        # expressions, and those that are unknown in all of its children.
        if entry.length is not None:
            unreferenced_entries[entry].update(self._collect_references(entry.length))
        elif isinstance(entry, sof.SequenceOf) and entry.count is not None:
            unreferenced_entries[entry].update(self._collect_references(entry.count))

        # Store the names the child doesn't know about (ie: names that must be resolved for this entry to decode)
        child_unknowns = set()
        for child in entry.children:
            child_unknowns.update(unreferenced_entries[child])

        if isinstance(entry, seq.Sequence) and entry.value is not None:
            # A sequence's references are treated as child unknowns, as they
            # are resolved from within the entry (and not passed in).
            child_unknowns.update(self._collect_references(entry.value))

        # Our unknown list is all the unknowns in our children that aren't
        # present in our known references.
        self._locals[entry] = set()
        child_names = [child.name for child in entry.children]
        for unknown in child_unknowns:
            name = unknown.name.split('.')[0]
            if name in child_names:
                # This value is a local...
                self._locals[entry].add(unknown)
                pass
            else:
                # This value is 'unknown' to the entry, and must be passed in.
                unreferenced_entries[entry].add(unknown)

        for reference in unreferenced_entries[entry]:
            self._params[entry].add(_VariableParam(reference, Param.IN))

    def _get_local_reference(self, entry, child, param):
        """Get the local name of a parameter used by a child entry. """
        if param.direction == Param.OUT and child.name != param.reference.name and not isinstance(entry, chc.Choice):
            name = "%s.%s" % (child.name, param.reference.name)
        else:
            name = param.reference.name

        # Create a new instance of the expression reference, using the new name
        return param.reference.__class__(name)

    def _detect_unused_outputs(self):
        """ Detect child parameters that aren't in the parent entries parameters """
        for entry, params in self._params.iteritems():

            for child in entry.children:
                for param in self._params[child]:
                    local = self._get_local_reference(entry, child, param)
                    if _VariableParam(local, param.direction) not in params:
                        self._locals[entry].add(local)

    def _detect_out_params(self):
        """ Add output parameters for all entries. """
        # Now that we have the locals, drill down into the relevant children
        # to pass the params as outputs.
        for entry, locals in self._locals.iteritems():
            for reference in locals:
                self._add_out_params(entry, reference)

        # We re-run the local detection, to find detect any 'unused' output parameters
        self._detect_unused_outputs()

    def _add_out_params(self, entry, reference):
        """
        Drill down into the children of 'entry', adding output params to 'name'.
        """
        if isinstance(entry, chc.Choice):
            # The option names aren't specified in a choice expression
            for child in entry.children:
                self._params[child].add(_VariableParam(reference, Param.OUT))
                self._add_out_params(child, reference)
        elif isinstance(entry, seq.Sequence):
            was_child_found = False
            for child in entry.children:
                if child.name == reference.name:
                    # This parameter references the value / length of the child item
                    self._params[child].add(_VariableParam(reference, Param.OUT))
                    was_child_found = True
                    if isinstance(reference, expr.ValueResult):
                        if isinstance(child, fld.Field):
                            if child.format not in [fld.Field.INTEGER, fld.Field.BINARY]:
                                # We currently only allow integers and binary
                                # strings in integer expressions.
                                raise BadReferenceTypeError(child)
                            self._referenced_values.add(child)
                        elif isinstance(child, seq.Sequence) and child.value is not None:
                            self._referenced_values.add(child)
                        else:
                            raise BadReferenceError(entry, reference.name)
                    else:
                        self._referenced_lengths.add(child)
                else:
                    child_name = reference.name.split('.')[0]
                    if child.name == child_name:
                        sub_name = ".".join(reference.name.split('.')[1:])
                        if isinstance(reference, expr.ValueResult):
                            child_reference = expr.ValueResult(sub_name)
                        elif isinstance(reference, expr.LengthResult):
                            child_reference = expr.LengthResult(sub_name)
                        else:
                            raise Exception("Unknown reference type '%s'!" % reference)

                        # We found a child item that knows about this parameter
                        self._params[child].add(_VariableParam(child_reference, Param.OUT))
                        self._add_out_params(child, child_reference)
                        was_child_found = True
            if not was_child_found:
                raise ent.MissingExpressionReferenceError(entry, reference.name)
        else:
            raise BadReferenceError(entry, reference.name)

    def get_locals(self, entry):
        """
        Get the names of local variables used when decoding an entry.

        Local variables are all child outputs that aren't an output of the
        entry.
        """
        result = list(set(self._get_reference_name(reference) for reference in self._locals[entry]))
        result.sort()
        return result

    def get_params(self, entry):
        """
        Get an iterator to all parameters passed to an entry due to value references.
        """
        params = list(self._params[entry])
        params.sort(key=lambda a:a.reference.name)
        result = list(Param(self._get_reference_name(param.reference), param.direction, int) for param in params)
        return result

    def _get_reference_name(self, reference):
        if isinstance(reference, expr.ValueResult):
            return reference.name
        elif isinstance(reference, expr.LengthResult):
            return reference.name + ' length'
        raise Exception("Unknown reference type '%s'" % reference)

    def get_passed_variables(self, entry, child):
        """
        Get an iterator to all variables passed from a parent to a child entry.
        """
        child_params = list(self._params[child])
        child_params.sort(key=lambda a:a.reference.name)
        for param in child_params:
            local = self._get_local_reference(entry, child, param)
            yield Param(self._get_reference_name(local), param.direction, int)

    def is_value_referenced(self, entry):
        """ Is the decoded value of an entry used elsewhere. """
        return entry in self._referenced_values

    def is_length_referenced(self, entry):
        """ Is the decoded length of an entry used elsewhere. """
        return entry in self._referenced_lengths


class ResultParameters(_Parameters):
    """
    A class that generates the parameters used when passing the decode result
    out of the decode function as a parameter.
    """
    def __init__(self, entries):
        pass

    def get_locals(self, entry):
        # Result items are never stored as locals; they are always passed out.
        return []

    def get_params(self, entry):
        if entry.is_hidden():
            return []
        return [Param('result', Param.OUT, entry)]

    def get_passed_variables(self, entry, child):
        if child.is_hidden():
            return []
        return [Param('unknown', Param.OUT, child)]


class CompoundParameters(_Parameters):
    """
    Class to return the results of several other parameter query classes
    through one instance.
    """
    def __init__(self, parameter_queries):
        self._queries = parameter_queries

    def get_locals(self, entry):
        for query in self._queries:
            for local in query.get_locals(entry):
                yield local

    def get_params(self, entry):
        for query in self._queries:
            for param in query.get_params(entry):
                yield param

    def get_passed_variables(self, entry, child):
        for query in self._queries:
            for param in query.get_passed_variables(entry, child):
                yield param

    def is_end_sequenceof(self, entry):
        for query in self._queries:
            if query.is_end_sequenceof(entry):
                return True
        return False

    def is_value_referenced(self, entry):
        for query in self._queries:
            if query.is_value_referenced(entry):
                return True
        return False

    def is_length_referenced(self, entry):
        for query in self._queries:
            if query.is_length_referenced(entry):
                return True
        return False

