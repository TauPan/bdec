import StringIO
import xml.sax

import dcdr.data as dt
import dcdr.field as fld
import dcdr.load
import dcdr.sequence as seq

class _Handler(xml.sax.handler.ContentHandler):
    """
    A sax style xml handler for building a decoder from an xml specification
    """
    def __init__(self):
        self._stack = []
        self._children = []

        self._handlers = {
            "field" : self._field,
            "protocol" : self._protocol,
            "sequence" : self._sequence
            }
        self.decoder = None

    def setDocumentLocator(self, locator):
        self._locator = locator

    def startElement(self, name, attrs):
        self._stack.append((name, attrs))
        self._children.append([])

    def endElement(self, name):
        assert self._stack[-1][0] == name
        (name, attrs) = self._stack.pop()
        if name not in self._handlers:
            raise dcdr.load.LoadError("Unrecognised element '%s'!" % name)

        children = self._children.pop()
        child = self._handlers[name](attrs, children)
        if len(self._children) > 0:
            self._children[-1].append(child)

    def _protocol(self, attributes, children):
        if len(children) != 1:
            raise xml.load.LoadError("Protocol should have a single entry to be decoded!")
        self.decoder = children[0]

    def _field(self, attributes, children):
        name = attributes['name']
        length = int(attributes['length'])
        format = fld.Field.BINARY
        if 'type' in attributes:
            lookup = {
                "binary" : fld.Field.BINARY,
                "hex" : fld.Field.HEX,
                "integer" : fld.Field.INTEGER,
                "text" : fld.Field.TEXT,
                }
            format = lookup[attributes['type']]
        encoding = None
        if 'encoding' in attributes:
            encoding = attributes['encoding']
        expected = None
        if 'value' in attributes:
            expected = dt.Data.from_hex(attributes['value'])
        return fld.Field(name, lambda: length, format, encoding, expected)

    def _sequence(self, attributes, children):
        return seq.Sequence(attributes['name'], children)


class Importer:
    """
    Class to create a decoder from an xml specification
    """

    def loads(self, xml):
        """
        Parse an xml data stream, interpreting it as a protocol
        specification.
        """
        return self.load(StringIO.StringIO(xml))

    def load(self, file):
        """
        Read a string from open file and interpret it as an
        xml data stream identifying a protocol entity.

        @return Returns a decoder entry.
        """
        parser = xml.sax.make_parser()
        handler = _Handler()
        parser.setContentHandler(handler)
        parser.parse(file)
        return handler.decoder
