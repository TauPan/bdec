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

import getopt
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
    usage = """
   %prog [-V] [-t <template dir>] <spec_filename> [output_dir]

Compile bdec specifications into language specific decoders

Arguments:'
   spec_filename -- The filename of the specification to be compiled
   output_dir -- The directory to save the generated source code. If not
                 specified the current working directory will be used"""
    parser = OptionParser(usage=usage)
    parser.add_option("-t", "--template", dest="template",
                      help="Set the template to compile. If there is a directory with the specified name, it will be used as the template directory. Otherwise it will use the internal template with the specified name. If not specified a C language decoder will be compiled")
    parser.add_option("-V", "--version", dest="version", action="store_true",
                      help="Print the version of the bdec compiler and exit",
                      default=False)
    (options, args) = parser.parse_args()
    if options.version:
        print bdec.__version__
        sys.exit(0)
    if len(args) < 1:
        parser.error("You must give at least a specification. Please review --help.")
    elif len(args) > 2:
        parser.error("Too many arguments. Please review --help.")
    return (options, args)


def main():
    outputdir = None
    template_dir = None

    (options, args) = parse_arguments()

    spec, common, lookup = _load_spec(args[0])

    if len(args) == 2:
        outputdir = args[1]
    else:
        outputdir = os.getcwd()

    if options.template:
        if os.path.exists(arg):
            template_dir = bdec.compiler.FilesystemTemplate(arg)
        else:
            template_dir = bdec.compiler.BuiltinTemplate(arg)
    else:
        template_dir = bdec.compiler.BuiltinTemplate('c')

    try:
        templates = bdec.compiler.load_templates(template_dir)
        bdec.compiler.generate_code(spec, templates, outputdir, common.itervalues())
    except:
        sys.exit(mako.exceptions.text_error_template().render())

if __name__ == '__main__':
    main()

