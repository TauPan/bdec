import bdec.data as dt
import bdec.entry

class InvalidSequenceOfCount(bdec.DecodeError):
    """Raised during encoding when an invalid length is found."""
    def __init__(self, seq, expected, actual):
        bdec.DecodeError.__init__(self, seq)
        self.sequenceof = seq
        self.expected = expected
        self.actual = actual

    def __str__(self):
        return "%s expected count of %i, got %i" % (self.sequenceof, self.expected, self.actual)

class NegativeSequenceofLoop(bdec.DecodeError):
    """Error when a sequenceof is asked to loop a negative amount."""
    def __init__(self, seq, count):
        bdec.DecodeError.__init__(self, seq)
        self.count = count

    def __str__(self):
        return "%s asked to loop %i times!" % (self.entry, self.count)

class SequenceOf(bdec.entry.Entry):
    """
    A protocol entry representing a sequence of another protocol entry.

    The number of times the child entry will loop can be set in one of three
    ways;
     
     * It can loop for a specified amount of times
     * It can loop until a buffer is empty
     * It can loop until a child entry decodes
    """
    STOPPED = "stopped"
    ITERATING = "iterating"
    STOPPING = "stopping"

    def __init__(self, name, child, count, length=None, end_entries=[]):
        """
        count -- The number of times the child will repeat. If this value is
          None, the count will not be used.
        length -- The size of the buffer in bits. When the buffer is empty, the
          looping will stop. If None, the length will not be used.
        end_entries -- A list of child entries whose successful decode
          indicates the loop should stop.

        If neither count, length, or end_entries are used, the SequenceOf will
        fail to decode after using all of the available buffer.
        """
        bdec.entry.Entry.__init__(self, name, length, [child])
        self.count = count
        self.end_entries = end_entries

    def validate(self):
        bdec.entry.Entry.validate(self)
        for entry in self.end_entries:
            assert isinstance(entry, bdec.entry.Entry), "%s isn't an entry instance!" % str(entry)

    def _loop(self, context, data):
        context['should end'] = False
        if self.count is not None:
            count = int(bdec.entry.hack_calculate_expression(self.count, context))
            if count < 0:
                raise NegativeSequenceofLoop(self, count)

            for i in range(count):
                yield i
        elif self.length is not None:
            while 1:
                if data.empty():
                    # We ran out of data on a greedy sequence...
                    break
                yield None
        else:
            while 1:
                if context['should end']:
                    break
                yield None

    def _decode(self, data, context):
        yield (True, self, data, None)
        for i in self._loop(context, data):
            for item in self._decode_child(self.children[0], data, context):
                yield item
        yield (False, self, dt.Data(), None)

    def _encode(self, query, parent):
        children = self._get_context(query, parent)

        count = 0
        for child in children:
            count += 1
            for data in self.children[0].encode(query, child):
                yield data

        if self.count is not None and int(self.count) != count:
            raise InvalidSequenceOfCount(self, self.count, count)

