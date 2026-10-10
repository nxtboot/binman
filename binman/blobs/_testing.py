# SPDX-License-Identifier: GPL-2.0+
# Copyright 2026 Canonical Ltd
# Written by Simon Glass <simon.glass@canonical.com>
#
"""Blob handler used for testing

This is not a real blob handler, just one used for testing"""

import os
import tempfile

from binman import blob


# pylint: disable=C0103
class Blob_testing(blob.Blob):
    """Blob handler used for testing"""

    def __init__(self, compatible):
        super().__init__(compatible, 'testing blob handler')
        self.build_result = None
        self.fetch_result = None

    def build(self, version, arch, plat):
        """Build method that returns a configurable result for testing"""
        if self.build_result is not None:
            return self.build_result

        # By default, create a test file
        tmpdir = tempfile.mkdtemp(prefix='blobtest.')
        fname = os.path.join(tmpdir, 'test.bin')
        with open(fname, 'wb') as f:
            f.write(b'test blob content')
        return fname, tmpdir
