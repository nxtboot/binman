#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+

# Copyright (c) 2016 Google, Inc
# Written by Simon Glass <sjg@chromium.org>
#
# Creates binary images from input files controlled by a description
#

"""See README for more information"""

import os
import sys
import traceback

# Allow running directly from a checkout ('python3 binman/main.py'), so that
# 'from binman import ...' and the sibling packages resolve
# pylint: disable=C0413
our_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(2, os.path.dirname(our_path))

from binman import bintool
from binman import cmdline
from binman import control
from u_boot_pylib import test_util

def RunTests(debug, verbosity, processes, test_preserve_dirs, args, toolpath):
    """Run the functional tests and any embedded doctests

    Args:
        debug: True to enable debugging, which shows a full stack trace on error
        verbosity: Verbosity level to use
        test_preserve_dirs: True to preserve the input directory used by tests
            so that it can be examined afterwards (only useful for debugging
            tests). If a single test is selected (in args[0]) it also preserves
            the output directory for this test. Both directories are displayed
            on the command line.
        processes: Number of processes to use to run tests (None=same as #CPUs)
        args: List of positional args provided to binman. This can hold a test
            name to execute (as in 'binman test testSections', for example)
        toolpath: List of paths to use for tools
    """
    from binman import bintool_test
    from binman import blob_test
    from binman import cbfs_util_test
    from binman import elf_test
    from binman import entry_test
    from binman import fdt_test
    from binman import fip_util_test
    from binman import ftest
    from binman import image_test
    from binman import blobstore
    import doctest

    # Keep the tests away from the user's blob configuration, so that it does
    # not affect them. Tests which need a configuration provide their own
    blobstore.USER_CONFIG = '/nonexistent/blobstores.yaml'
    os.environ.pop(blobstore.CONFIG_ENV, None)

    test_name = args and args[0] or None

    # Run the entry tests first ,since these need to be the first to import the
    # 'entry' module.
    result = test_util.run_test_suites(
        'binman', debug, verbosity, False, test_preserve_dirs, processes,
        test_name, toolpath,
        [bintool_test.TestBintool, blob_test.TestBlob, blob_test.TestBlobFunctional,
         blob_test.TestBlobFiles, blob_test.TestBlobYamlConfig,
         entry_test.TestEntry, ftest.TestFunctional,
         fdt_test.TestFdt, elf_test.TestElf, image_test.TestImage,
         cbfs_util_test.TestCbfs, fip_util_test.TestFip])

    return (0 if result.wasSuccessful() else 1)

def RunTestCoverage(toolpath, build_dir, args):
    """Run the tests and check that we get 100% coverage"""
    glob_list = control.GetEntryModules(False)
    all_set = set([os.path.splitext(os.path.basename(item))[0]
                   for item in glob_list if '_testing' not in item])
    extra_args = ''
    if toolpath:
        for path in toolpath:
            extra_args += ' --toolpath %s' % path

    test_util.run_test_coverage(os.path.join(our_path, 'main.py'), None,
            ['*test*', '*main.py', '*/dtoc/*', '*/u_boot_pylib/*'],
            build_dir, all_set, extra_args or None, args=args,
            test_cmd='test')

def RunBinman(args):
    """Main entry point to binman once arguments are parsed

    Args:
        args: Command line arguments Namespace object
    """
    ret_code = 0

    if not args.debug:
        sys.tracebacklimit = 0

    # Provide a default toolpath in the hope of finding a mkimage built from
    # current source
    if not args.toolpath:
        args.toolpath = ['./tools', 'build-sandbox/tools']

    if args.cmd == 'test':
        if args.test_coverage:
            RunTestCoverage(args.toolpath, args.build_dir, args.tests)
        else:
            ret_code = RunTests(args.debug, args.verbosity, args.processes,
                                args.test_preserve_dirs, args.tests,
                                args.toolpath)
            if args.debug and not test_util.use_concurrent:
                print('Tests can run in parallel: pip install concurrencytest')

    elif args.cmd == 'bintool-docs':
        control.write_bintool_docs(bintool.Bintool.get_tool_list())

    elif args.cmd == 'entry-docs':
        control.WriteEntryDocs(control.GetEntryModules())

    else:
        try:
            ret_code = control.Binman(args)
        except Exception as e:
            print('binman: %s' % e, file=sys.stderr)
            if args.debug:
                print()
                traceback.print_exc()
            ret_code = 1
    return ret_code


def start_binman():
    args = cmdline.ParseArgs(sys.argv[1:])

    ret_code = RunBinman(args)
    sys.exit(ret_code)


if __name__ == "__main__":
    start_binman()
