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


<<<<<<< HEAD
def usage(program):
    print 'Compile bdec specifications into language specific decoders.'
    print 'Usage:'
    print '   %s [options] <spec_filename> [spec_filename] ...' % program
    print
    print 'Arguments:'
    print '   spec_filename -- The filename of the specification to be compiled.'
    print
    print 'Options:'
    print '  -h, --help        Print this help.'
    print '  -d <directory>    Directory to save the generated source code. Defaults'
    print '                    to %s.' % os.getcwd()
    print '  --encoder         Generate an encoder as well as a decoder.'
    print '  --main=<name>     Specify the entry to be use as the default decoder.'
    print '  --remove-unused   Remove any entries that are not referenced from the'
    print '                    main entry.'
    print '  --template=<name> Set the template to compile. If there is a directory'
    print '                    with the specified name, it will be used as the'
    print '                    template directory. Otherwise it will use the internal'
    print '                    template with the specified name. If not specified a'
    print '                    C language decoder will be compiled.'
    print '  -V                Print the version of the bdec compiler.'

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'd:hV', ['encoder', 'help', 'main=', 'remove-unused', 'template='])
    except getopt.GetoptError, ex:
        sys.exit("%s.\nRun '%s -h' for correct usage." % (ex, sys.argv[0]))
=======
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
    parser.add_option("--generate-line-pragmas", dest="line_pragmas",
                      action="store_true", default=False,
                      help='Generate #line <n> \"<source file>\" pragmas for c code. These are sometimes helpful in tracking down problems in the templates, but make the generated code a lot less human-readable. Defaults to False.')
    (options, args) = parser.parse_args()
    if options.version:
        print bdec.__version__
        sys.exit(0)
    if len(args) < 1:
        parser.error("You must give at least one specification. Please review --help.")
    return (options, args)


def main():
    (options, args) = parse_arguments()
>>>>>>> master

    template_dir = None
<<<<<<< HEAD
    outputdir = os.getcwd()
    should_remove_unused = False
    options = {
            'generate_encoder' : False
            }
    for opt, arg in opts:
        if opt == '-d':
            outputdir = arg
        elif opt == '--encoder':
            options['generate_encoder'] = True
        elif opt in ['-h', '--help']:
            usage(sys.argv[0])
            sys.exit(0)
        elif opt == '--main':
            main_spec = arg
        elif opt == '-V':
            print bdec.__version__
            sys.exit(0)
        elif opt == '--remove-unused':
            should_remove_unused = True
        elif opt == '--template':
            if os.path.exists(arg):
                template_dir = bdec.compiler.FilesystemTemplate(arg)
            else:
                template_dir = bdec.compiler.BuiltinTemplate(arg)
        elif opt == '--main':
            main_spec = arg
        else:
            assert False, 'Unhandled option %s!' % opt
=======
    if options.template and os.path.exists(options.template):
        template_dir = bdec.compiler.FilesystemTemplate(options.template)
    else:
        template_dir = bdec.compiler.BuiltinTemplate('c')

    options.template = template_dir
>>>>>>> master

    try:
        spec, common, lookup = load_specs([(s, None, None) for s in args], options.main, options.remove_unused)
    except bdec.spec.LoadError, ex:
        sys.exit(str(ex))

    try:
<<<<<<< HEAD
        templates = bdec.compiler.load_templates(template_dir)
        bdec.compiler.generate_code(spec, templates, outputdir, common, options)
=======
        templates = bdec.compiler.load_templates(options)
        bdec.compiler.generate_code(spec, templates, options.directory, common)
>>>>>>> master
    except:
        sys.exit(mako.exceptions.text_error_template().render())

if __name__ == '__main__':
    main()

