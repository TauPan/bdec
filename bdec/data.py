import bdec
import string

class DataError(Exception):
    """
    Base class for all data errors.
    """
    pass

class NotEnoughDataError(DataError):
    def __init__(self, requested_length, available_length):
        self.requested = requested_length
        self.available = available_length

    def __str__(self):
        return "Asked for %i bits, but only have %i bits available!" % (self.requested, self.available)

class PoppedNegativeBitsError(DataError):
    def __init__(self, requested_length):
        self.requested = requested_length
        assert self.requested < 0

    def __str__(self):
        return "Data source asked for %i bits!" % self.requested

class IntegerTooLongError(DataError):
    def __init__(self, value, length):
        self.value = value
        self.length = length

    def __str__(self):
        return "Cannot encode value %i in %i bits" % (self.value, self.length)

class HexNeedsFourBitsError(DataError):
    """ Raised when attempting to convert data to hex, and we don't
        have a multiple of 4 bits. """
    pass

class ConversionNeedsBytesError(DataError):
    pass

class InvalidBinaryTextError(DataError):
    pass

class InvalidHexTextError(DataError):
    pass

class _OutOfDataError(Exception):
    """Not derived from DataError as this is an internal error."""

# Note that we don't include 'x' in the hex characters...
_HEX_CHARACTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'A', 'B', 'C', 'D', 'E', 'F', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']


class _MemoryBuffer:
    def __init__(self, buffer):
        self._buffer = buffer

    def read_byte(self, offset):
        """Read a byte at a given offset"""
        if offset >= len(self._buffer):
            raise _OutOfDataError()
        return ord(self._buffer[offset])


class Data:
    """ A class to hold data to be decoded """
    def __init__(self, buffer="", start=None, end=None):
        if start is None:
            start = 0
        if end is None:
            end = len(buffer) * 8

        assert start <= end
        self._start = start
        self._end = end

        if isinstance(buffer, str):
            self._buffer = _MemoryBuffer(buffer)
        else:
            assert isinstance(buffer, _MemoryBuffer)
            self._buffer = buffer

    def pop(self, length):
        """
        Pop data from this data object.
        """
        if length < 0:
            raise PoppedNegativeBitsError(length)
        if length > self._end - self._start:
            raise NotEnoughDataError(length, self._end - self._start)

        result = Data(self._buffer, self._start, self._start + length)
        self._start += length
        return result

    def copy(self):
        return Data(self._buffer, self._start, self._end)

    def __str__(self):
        return "".join(chr(byte) for byte in self._get_bytes())

    def _get_bits(self):
        """
        Get an iterator to the bits contained in this buffer.
        """
        i = 0
        while 1:
            try:
                yield self._get_bit(i + self._start)
            except _OutOfDataError:
                break
            i += 1

    def __eq__(self, other):
        if not isinstance(other, Data):
            return NotImplemented

        # TODO: This bit by bit comparison is slow...
        a = self._get_bits()
        b = other._get_bits()
        while 1:
            try:
                a_bit = a.next()
            except StopIteration:
                try:
                    b.next()
                    # Not equal, as 'other' is longer then we are
                    return False
                except StopIteration:
                    # Equal, as same size, same values
                    return True

            try:
                b_bit = b.next()
            except StopIteration:
                # Not equal, as we are longer than 'other'
                return False

            if a_bit != b_bit:
                return False

    def __ne__(self, other):
        if not isinstance(other, Data):
            return NotImplemented

        return not self == other

    def __len__(self):
        if self._end is not None:
            return self._end - self._start
        # TODO: We don't need to create a list of the bits; we only need to count them.
        # We don't know the end, so we'll have to iterate over the whole lot to find it.
        return len(list(self._get_bits()))

    def _get_bit(self, i):
        """
        Query the backend byte source for a given bit.

        If the backend doesn't have the data available, or we are querying
        outside of our bounds, an _OutOfDataError is raised.
        """
        assert i >= self._start
        if self._end is not None and i >= self._end:
            raise _OutOfDataError()
        byte = i / 8
        i = i % 8
        return (self._buffer.read_byte(byte) >> (7 - i)) & 1
        
    def __int__(self):
        """
        Convert the buffer to an integer

        Conversion is big endian.
        """
        result = 0
        for bit in self._get_bits():
            result = (result << 1) | bit
        return result

    def __add__(self, other):
        if not isinstance(other, Data):
            return NotImplemented
        # Incredibly inefficient...
        return Data.from_binary_text(self.get_binary_text() + other.get_binary_text())

    def _get_bytes(self):
        """
        Return an iterator to a series of byte values in the data.
        """
        # TODO: Optimise reading when we are byte aligned...

        # Read as many of the bits as possible, yielding the results.
        value = 0
        i = None
        for i, bit in enumerate(self._get_bits()):
            value = (value << 1) | bit
            if (i + 1) % 8 == 0:
                # We have a new byte!
                yield value
                value = 0
        if i is not None and i % 8 != 7:
            raise ConversionNeedsBytesError()

    def get_little_endian_integer(self):
        """
        Get an integer that has been encoded in little endian format
        """
        result = 0
        for byte, value in enumerate(self._get_bytes()):
            result = result | (value << (8 * byte))
        return result

    def get_binary_text(self):
        """
        Get a string representing the binary data.

        eg: 001 10100000
        """
        bits = list(self._get_bits())
        bytes = []
        if len(bits) % 8 != 0:
            bytes.append(bits[0:len(bits) % 8])
        for i in range(len(bits) % 8, len(bits), 8):
            bytes.append(bits[i:i+8])

        bytes = ("".join(str(bit) for bit in byte) for byte in bytes)
        return " ".join(byte for byte in bytes)

    def get_hex(self):
        """
        Get a string representing the data in hex format.
        """
        bits = list(self._get_bits())
        if len(bits) % 4 != 0:
            raise HexNeedsFourBitsError(self)

        chars = []
        for i in range(0, len(bits), 4):
            value = 0
            for bit in range(4):
                value |= bits[i + bit] << (3-bit)
            chars.append(hex(value)[2:])
        return "".join(chars)

    @staticmethod
    def from_int_little_endian(value, length):
        data = int(value)
        if length % 8 != 0:
            raise ConversionNeedsBytesError()
        chars = []
        for i in range(length / 8):
            chars.append(chr(data & 0xff))
            data >>= 8
        if data != 0:
            raise IntegerTooLongError(value, length)
        return Data("".join(chars))

    @staticmethod
    def from_int_big_endian(value, length):
        data = int(value)
        chars = []
        num_bytes = length / 8
        if length % 8 != 0:
            num_bytes += 1
        for i in range(num_bytes):
            chars.append(chr(data & 0xff))
            data >>= 8
        if data != 0:
            raise NotEnoughDataError(value, length)
        chars.reverse()

        result = Data("".join(chars))
        if 0 != int(result.pop(num_bytes * 8 - length)):
            # We have an integer that isn't a multiple of 8 bits, and we
            # couldn't quite fit it in the space available.
            raise IntegerTooLongError(value, length)
        return result

    @staticmethod
    def from_hex(hex): 
        """
        Convert a hex string to a data buffer.

        The hex entries can be seperated by whitespace, with multi-byte entries
        seperated on even characters.  For example, '0e 9a bc', or '0e9abc'.

        Entries without whitespace with an odd number of characters will be 
        treated as if it had a leading zero; eg: 'e02' will be interpreted as
        being the two byte value '0e02'.
        """
        buffer = []
        entries = hex.split()
        for entry in entries:
            if len(entry) % 2:
                entry = '0' + entry

            for i in range(len(entry) / 2):
                offset = i * 2
                value = entry[offset:offset + 2]
                for char in value:
                    if char not in _HEX_CHARACTERS:
                        raise InvalidHexTextError(hex)
                buffer.append(int(value, 16))
        return Data("".join(chr(value) for value in buffer))

    @staticmethod
    def from_binary_text(text):
        """
        Create a data object from binary text.

        eg: "001 10100000"
        """
        buffer = []
        value = 0
        length = 0
        for char in text:
            if char not in string.whitespace:
                if char not in ['0', '1']:
                    raise InvalidBinaryTextError("Invalid binary text!", text)
                value <<= 1
                value |= int(char)
                length += 1

                if length == 8:
                    buffer.append(chr(value))
                    length = 0
                    value = 0
        buffer.append(chr(value << (8 - length)))
        return Data("".join(buffer), 0, len(buffer) * 8 - (8 - length))


