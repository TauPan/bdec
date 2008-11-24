
import logging
import sys

import bdec
import bdec.data as dt
import bdec.spec.xmlspec as xmlspec
import bdec.output.xmlout as xmlout

def _parse_args():
    spec = None
    binary = None
    verbose = False
    log = False
    for arg in sys.argv[1:]:
        if arg == '--verbose':
            verbose = True
        elif arg == "-l":
            log = True
        elif spec is None:
            spec = arg
        elif binary is None:
            binary = file(arg, 'rb')
        else:
            sys.exit('Too many arguments!')

    if log:
        logging.basicConfig(level=logging.INFO)

    if spec is None:
        sys.exit('Specification not set!')

    if binary is None:
        binary = sys.stdin.read()
    data = dt.Data(binary)

    return (spec, data, verbose)

def main():
    spec, data, verbose = _parse_args()
    try:
        decoder, lookup, common = xmlspec.load(spec)
    except bdec.spec.LoadError, ex:
        sys.exit(str(ex))

    try:
        xmlout.to_file(decoder, data, sys.stdout, verbose=verbose)
    except bdec.DecodeError, ex:
        (filename, line_number, column_number) = lookup[ex.entry]
        sys.exit("%s[%i]: %s" % (filename, line_number, str(ex)))

    try:
        # Test to see if we have data undecoded...
        remaining = data.pop(1)

        try:
            # Only attempt to display the first 8 bytes; more isn't particularly
            # useful.
            remaining = remaining + data.copy().pop(8 * 8 - 1)
            sys.stderr.write('Over 8 bytes undecoded!\n')
        except dt.NotEnoughDataError:
            remaining = remaining + data
            sys.stderr.write('Data is still undecoded!\n')
        sys.stderr.write(str(remaining) + '\n')
    except dt.NotEnoughDataError:
        # All the data has been decoded.
        pass