import bdec.data as dt
import bdec.entry

class Sequence(bdec.entry.Entry):
    """
    A sequence type protocol entry.

    A sequence protocol entry is made up of multiple other
    entry types, and they are decoded one after the other.
    All of the child protocol entries must be decoded for
    the sequence to successfully decode.

    A sequence object may be assigned a value, derived from
    the child elements. This allows techniques such as
    lookup tables, and alternate integer encoding methods.
    """

    def __init__(self, name, children, value=None, length=None):
        bdec.entry.Entry.__init__(self, name, length, children)
        self.value = value

    def _decode(self, data, context):
        yield (True, self, data, None)
        for child in self.children:
            for embedded in self._decode_child(child, data, context):
                yield embedded
        yield (False, self, dt.Data(), None)

    def _encode(self, query, parent):
        structure = self._get_context(query, parent)
        for child in self.children:
            for data in child.encode(query, structure):
                yield data
            
    def _range(self, ignore_entries):
        return sum((child.range(ignore_entries) for child in self.children), bdec.entry.Range(0, 0))
