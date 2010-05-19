#   Copyright (C) 2008 Henry Ludemann
#
#   This file is part of the bdec decoder library.
#
#   The bdec decoder library is free software; you can redistribute it
#   and/or modify it under the terms of the GNU Lesser General Public
#   License as published by the Free Software Foundation; either
#   version 2.1 of the License, or (at your option) any later version.
#
#   The bdec decoder library is distributed in the hope that it will be
#   useful, but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public
#   License along with this library; if not, see
#   <http://www.gnu.org/licenses/>.

import logging
import sys

from optparse import OptionParser

import bdec
import bdec.data as dt
import bdec.inspect.param
import bdec.output.xmlout as xmlout
from bdec.spec import load

def parse_arguments():
    usage = "usage: %prog [-lv] <specification> [binary]"
    parser = OptionParser(usage=usage)
    parser.add_option("-v", "--verbose", dest="verbose",
                      help="gives more verbose output", default=False)
# TODO: give better help text when understood
    parser.add_option("-l", "--log", dest="log",
                      help="do logging", default=False)
    (options, args) = parser.parse_args()
    if len(args) < 1:
        parser.error("No specification and binary files given. Please review --help.")
    elif len(args) > 2:
        parser.error("Too many arguments. Please review --help.")
    spec = args[0]
    binary = None
    if len(args) == 2:
        binary = file(args[1], 'rb')
    else:
        binary = sys.stdin
    if options.log:
        logging.basicConfig(level=logging.INFO)
    verbose = options.verbose
    return (spec, binary, verbose)


def main():
    spec, binary, verbose = parse_arguments()
    try:
        decoder, common, lookup = load(spec)
        bdec.spec.validate_no_input_params(decoder, lookup)
    except bdec.spec.LoadError, ex:
        sys.exit(str(ex))

    data = dt.Data(binary)
    try:
        xmlout.to_file(decoder, data, sys.stdout, verbose=verbose)
    except bdec.DecodeError, ex:
        try:
            (filename, line_number, column_number) = lookup[ex.entry]
        except KeyError:
            (filename, line_number, column_number) = ('unknown', 0, 0)

        # We include an extra new line, as the xml is unlikely to have finished
        # on a new line (issue164).
        print
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

if __name__ == '__main__':
    main()

