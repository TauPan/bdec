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
        assert len(children) > 0
        for child in children:
            assert isinstance(child, bdec.entry.Entry)

    def _decode(self, data, child_context):
        yield (True, self, data, None)
        for child in self.children:
            for embedded in child.decode(data, child_context):
                yield embedded
        yield (False, self, dt.Data(), None)

    def _encode(self, query, parent):
        structure = self._get_context(query, parent)
        for child in self.children:
            for data in child.encode(query, structure):
                yield data
            
    def range(self):
        return sum((child.range() for child in self.children), bdec.entry.Range(0, 0))
