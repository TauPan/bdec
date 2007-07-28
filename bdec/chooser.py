import bdec.choice as chc
import bdec.data as dt
import bdec.field as fld
import bdec.sequence as seq

class _UnknownData:
    """
    A class representing data with an unknown value.
    """
    UNKNOWN_LENGTH = 100000000

    def __init__(self, length=None):
        self._length = length

    def pop(self, length):
        if self._length is not None:
            assert self._length >= length
            self._length -= length
        return _UnknownData(length)

    def __len__(self):
        if self._length is None:
            return self.UNKNOWN_LENGTH
        return self._length

    def copy(self):
        return _UnknownData(self._length)

class _ChoiceData:
    """A class representing a fork in the data stream. """
    def __init__(self, options):
        self.options = options

    def copy(self):
        return self


def _data_iter(entry):
    """
    Return an iterator to data objects in this protocol entry.
    """
    if isinstance(entry, fld.Field):
        if entry.expected is not None:
            yield entry.expected.copy()
        else:
            import bdec.spec.xmlspec
            length = None
            try:
                length = int(entry.length)
            except bdec.spec.xmlspec.UndecodedReferenceError:
                # If the length of a  field references the decoded value of
                # another field, we will not be able to calculate the length.
                pass
            yield _UnknownData(length)
    elif isinstance(entry, seq.Sequence):
        for child in entry.children:
            for child_entry in _data_iter(child):
                yield child_entry
    elif isinstance(entry, chc.Choice):
        yield _ChoiceData(entry.children)
    else:
        # We don't attempt to use other entry types when differentiating, as
        # earlier fields should have been enough.
        yield _UnknownData()

class _IterCache:
    """A class to cache results from an iterator."""
    def __init__(self, iter):
        self._iter = iter
        self._cache = []

    def __iter__(self):
        i = 0
        while 1:
            if i == len(self._cache):
                if self._iter is None:
                    break
                try:
                    self._cache.append(self._iter.next())
                except StopIteration:
                    self._iter = None
                    break

            assert 0 <= i < len(self._cache)
            yield self._cache[i].copy()
            i = i + 1


class _JoinIters:
    """A class to join two iterator results into one."""
    def __init__(self, a, b):
        self._a = a
        self._b = b

    def __iter__(self):
        for a in self._a:
            yield a
        for b in self._b:
            yield b


class _EntryData:
    """
    Class to walk over a protcol entry's expected data stream.
    """
    def __init__(self, entry, data_iter):
        self._data_iter = iter(data_iter)
        self._data = self._data_iter.next()
        self.entry = entry

    def data_length(self):
        return len(self._data)

    def pop_data(self, length):
        result = self._data.pop(length)
        if len(self._data) == 0:
            try:
                self._data = self._data_iter.next()
            except StopIteration:
                # When an option has no more data to be matched, we use
                # an unknown data object so it will still fall into
                # the 'undistinguished' categories in later matches.
                self._data = _UnknownData()
        return result

    def should_fork(self):
        return isinstance(self._data, _ChoiceData)

    def fork(self):
        """
        Handle a fork in the data stream.

        Returns a list of _EntryData objects representing the different
        possible paths in the data stream.
        """
        assert self.should_fork()
        post_choice_iter = _IterCache(self._data_iter)
        for option in self._data.options:
            iter = _JoinIters(_data_iter(option), post_choice_iter)
            yield _EntryData(self.entry, iter)

def _differentiate(entries):
    """
    Differentiate between protocol entries.

    Returns a list of (offset, length, lookup, undistinguished) entries, where
    lookup is a dictionary mapping value -> entries, and undistinguished is a
    list of entries that don't distinguish themselves on this entry.
    """
    offset = 0
    data_options = [_EntryData(entry, _data_iter(entry)) for entry in entries]
    while data_options:
        test_for_forks = True
        while test_for_forks:
            for option in data_options[:]:
                if option.should_fork():
                    data_options.remove(option)
                    data_options.extend(option.fork())
                    break
            else:
                test_for_forks = False

        # Calculate the length of the next section of 'differentiable' protocol
        # section.
        length = min(entry.data_length() for entry in data_options)
        if length == _UnknownData.UNKNOWN_LENGTH:
            # We cannot differentiate any more...
            break

        # Get the values of all of the options for this data section
        lookup = {}
        undistinguished = []
        for entry in data_options:
            data = entry.pop_data(length)
            if isinstance(data, _UnknownData):
                undistinguished.append(entry.entry)
            else:
                lookup.setdefault(int(data), []).append(entry.entry)

        if length:
            yield offset, length, lookup, undistinguished
        offset += length


class _Options:
    """
    A class to recursively drill down into data, identifying potential options.
    """
    def __init__(self, options, start_bit, order):
        # Identify unique entries in the available options starting
        # at the bit offset.
        self._options = None
        self._lookup = None
        self._fallback = None
        for offset, length, lookup, undistinguished in _differentiate(options):
            if offset >= start_bit and lookup and length:
                # We found a range of bits that can be used to distinguish
                # between the diffent options
                self._start_bit = offset
                self._length = length
                self._lookup = {}
                self._fallback = _Options(undistinguished, start_bit + length, order)
                for value, entries in lookup.iteritems():
                    self._lookup[value] = _Options(entries + undistinguished, offset + length, order)
                break
        else:
            # We were unable to differentiate between the protocol entries. Note
            # that we want to maintain the same original order.
            self._options = [option for option in order if option in set(options)]

    def choose(self, data):
        """
        Return a list of possible entries that matches the input data.

        The possible entries will be in the same order as the entries passed
        into the constructor.
        """
        if self._options is not None:
            # We are unable to narrow down the possibilities further.
            return self._options

        # We are able to potentially narrow down the possibilities based
        # on the input values.
        assert self._lookup
        copy = data.copy()
        try:
            copy.pop(self._start_bit)
            value = int(copy.pop(self._length))
        except dt.NotEnoughDataError:
            # We can't read this data to be keyed on, so we'll leave it
            # to one of the fallbacks.
            value = None
            options = self._fallback

        if value is not None:
            try:
                options = self._lookup[value]
            except KeyError:
                # The value present isn't one of the expected values; we'll
                # fallback to the options that could handle any value for
                # this bit offset.
                options = self._fallback
        return options.choose(data)

    def __repr__(self):
        # We have a representation option as it greatly simplifies debugging;
        # just print the option object to look at the tree.
        if self._options is not None:
            return str(self._options)
        return "bits [%i, %i) key=%s fallback=%s" % (self._start_bit, self._start_bit + self._length, repr(self._lookup), repr(self._fallback))

class Chooser(_Options):
    """
    Choose a protocol entry from a list of protocol entries that matches input data.

    This class attempts to quickly determine the type of protocol entry that can be
    decoded.
    """
    def __init__(self, entries):
        _Options.__init__(self, entries, 0, entries)
