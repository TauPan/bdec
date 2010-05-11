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

import mako.exceptions
import os
import sys

from optparse import OptionParser

import bdec.spec.xmlspec
import bdec.compiler

def _load_spec(filename):
    """Load the protocol specification. """
    try:
        decoder, common, lookup = bdec.spec.xmlspec.load(filename)
    except bdec.spec.LoadError, ex:
        sys.exit(str(ex))
    return decoder, common, lookup

def parse_arguments():
    usage = "usage: %prog [-t <template dir>] <specification> [output dir]"
    parser = OptionParser(usage=usage)
    parser.add_option("-t", "--template", dest="template",
                      help="choose a template directory", metavar="DIR")
    (options, args) = parser.parse_args()
    if len(args) < 1:
        parser.error("You must give at least a specification. Please review --help.")
    elif len(args) > 2:
        parser.error("Too many arguments. Please review --help.")
    return (options, args)


def main():
    (options, args) = parse_arguments()
    spec_file = args[0]
    spec, common, lookup = _load_spec(spec_file)
    if len(args) == 2:
        outputdir = args[1]
    else:
        outputdir = os.getcwd()

    language = 'c'
    try:
        bdec.compiler.generate_code(spec, language, outputdir, common.itervalues())
    except:
        sys.exit(mako.exceptions.text_error_template().render())

if __name__ == '__main__':
    main()

