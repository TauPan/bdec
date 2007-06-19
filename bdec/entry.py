import bdec
import bdec.data as dt

class MissingInstanceError(bdec.DecodeError):
    """
    Error raised during encoding when a parent object doesn't have a named child object.
    """
    def __init__(self, parent, child):
        bdec.DecodeError.__init__(self, child)
        self.parent = parent
        self.child = child

    def __str__(self):
        return "object '%s' doesn't have child object '%s'" % (self.parent, self.child.name)

class EntryDataError(bdec.DecodeError):
    def __init__(self, entry, ex):
        bdec.DecodeError.__init__(self, entry)
        self.ex = ex

    def __str__(self):
        return "%s - %s" % (self.entry, self.ex)

class BadDecodeLengthError(bdec.DecodeError):
    def __init__(self, entry, unused):
        bdec.DecodeError.__init__(self, entry)
        self.unused = unused

    def __str__(self):
        return "'%s' left %i bits of data undecoded (%s)" % (self.entry, len(self.unused), self.unused.get_binary_text())

class DataLengthError(bdec.DecodeError):
    """
    Encoded data has the wrong length
    """
    def __init__(self, entry, length, data):
        bdec.DecodeError.__init__(self, entry)
        self.length = length
        self.data = data

    def __str__(self):
        return "%s expected length %i, got length %i (%s)" % (self.entry, self.length, len(self.data), self.data.get_binary_text())

def is_hidden(name):
    """
    Is a name a 'hidden' name.

    Entries may be hidden for many reasons; for example, we don't want to
    see 'expected' results (that is, fields with data we expect, without
    which the decode would fail).
    """
    return name.endswith(':')

class Entry(object):
    """
    A decoder entry is an item in a protocol that can be decoded.

    An entry can have a length; if so, the decode size of that entry
    must match.
    """

    def __init__(self, name, length=None):
        self.name = name
        self._listeners = []
        self.length = length

    def add_listener(self, listener):
        """
        Add a listener to be called when the entry successfully decodes.

        The listener will be called with this entry, and the amount of data
        decoded as part of this entry (ie: this entry, and all of its
        children).

        Note that the listener will be called for every internal decode, not
        just the ones that are propageted to the user (for example, if an
        entry is in a choice that later fails to decode, the listener will
        still be notified).
        """
        self._listeners.append(listener)

    def _decode(self, data):
        """
        Decode the given protocol entry.

        Should return an iterable object for all of the 'embedded'
        protocol entries in the same form as Entry.decode.
        """
        raise NotImplementedError()

    def _decode_entry(self, data):
        yield (True, self)
        for (is_starting, entry) in self._decode(data):
            yield (is_starting, entry)
        yield (False, self)

    def decode(self, data):
        """
        Decode this entry from input data.

        @param data The data to decode
        @return An iterator that returns (is_starting, Entry) tuples.
        """
        if self.length is not None:
            try:
                data = data.pop(int(self.length))
            except dt.DataError, ex:
                raise EntryDataError(self, ex)

        import bdec.field as fld
        length = 0
        for is_starting, entry in self._decode_entry(data):
            if not is_starting and isinstance(entry, fld.Field):
                length += len(entry.data)
            yield is_starting, entry

        if self.length is not None and len(data) != 0:
            raise BadDecodeLengthError(self, data)

        for listener in self._listeners:
            listener(self, length)

    def _get_context(self, query, parent):
        # This interface isn't too good; it requires us to load the _entire_ document
        # into memory. This is because it supports 'searching backwards', plus the
        # reference to the root element is kept. Maybe a push system would be better?
        #
        # Problem is, push doesn't work particularly well for bdec.output.instance, nor
        # for choice entries (where we need to re-wind...)

        try:
            context = query(parent, self)
        except MissingInstanceError:
            if not self.is_hidden():
                raise
            # The instance wasn't included in the input, but as it is hidden, we'll
            # keep using the current context.
            context = parent_context
        return context

    def _encode(self, query, context):
        """
        Encode a data source, with the context being the data to encode.
        """
        raise NotImplementedError()

    def encode(self, query, parent_context):
        """
        Encode a data source.

        Sub-items will be queried by calling 'query' with a name and the context
        object. This query should raise a MissingInstanceError if the instance
        could not be found.
        
        Returns an iterator object for a series of data objects.
        """
        encode_length = 0
        for data in self._encode(query, parent_context):
            encode_length += len(data)
            yield data

        if self.length is not None and encode_length != int(self.length):
            raise DataLengthError(self, int(self.length), data)

    def is_hidden(self):
        """
        Is this a 'hidden' entry.
        """
        return is_hidden(self.name)
