#   Copyright (C) 2008-2010 Henry Ludemann
#   Copyright (C) 2010 PRESENSE Technologies GmbH
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

from bdec.spec import load_specs
import bdec.compiler


def parse_arguments():
    usage = """
   %prog [options] <spec_filename> [spec_filename] ...

Compile bdec specifications into language specific decoders

Arguments:'
   spec_filename -- The filename of the specification to be compiled
"""
    parser = OptionParser(usage=usage)
    parser.add_option("-t", "--template", dest="template", default=None,
                      help="Set the template to compile. If there is a directory with the specified name, it will be used as the template directory. Otherwise it will use the internal template with the specified name. If not specified a C language decoder will be compiled")
    parser.add_option("-V", "--version", dest="version", action="store_true",
                      help="Print the version of the bdec compiler and exit",
                      default=False)
    parser.add_option("-m", "--main", dest="main", default=None,
                      help="Specify the entry to be use as the default decoder.")
    parser.add_option("-r", "--remove-unused", dest="remove_unused",
                      action="store_true", default=False,
                      help="Remove any entries that are not referenced from the main entry.")
    parser.add_option("-d", "--directory", dest="directory", default=os.getcwd(),
                      help="Directory to save the generated source code. Defaults to %s." % os.getcwd())
    (options, args) = parser.parse_args()
    if options.version:
        print bdec.__version__
        sys.exit(0)
    if len(args) < 1:
        parser.error("You must give at least one specification. Please review --help.")
    return (options, args)


def main():
    (options, args) = parse_arguments()

    template_dir = None
    if options.template and os.path.exists(options.template):
        template_dir = bdec.compiler.FilesystemTemplate(options.template)
    else:
        template_dir = bdec.compiler.BuiltinTemplate('c')

    try:
        spec, common, lookup = load_specs([(s, None, None) for s in args], options.main, options.remove_unused)
    except bdec.spec.LoadError, ex:
        sys.exit(str(ex))

    try:
        templates = bdec.compiler.load_templates(template_dir)
        bdec.compiler.generate_code(spec, templates, options.directory, common)
    except:
        sys.exit(mako.exceptions.text_error_template().render())

if __name__ == '__main__':
    main()

