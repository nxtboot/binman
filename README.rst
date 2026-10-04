Binman firmware packager
========================

.. image:: https://github.com/nxtboot/binman/actions/workflows/test.yml/badge.svg
   :target: https://github.com/nxtboot/binman/actions/workflows/test.yml
   :alt: Test status

.. image:: https://img.shields.io/pypi/v/binary-manager.svg
   :target: https://pypi.org/project/binary-manager/
   :alt: PyPI version

.. image:: https://readthedocs.org/projects/binman/badge/?version=latest
   :target: https://binman.readthedocs.io/en/latest/
   :alt: Documentation status

.. image:: https://img.shields.io/pypi/pyversions/binary-manager.svg
   :target: https://pypi.org/project/binary-manager/
   :alt: Supported Python versions

Binman packages firmware. Building firmware should be separate from packaging
it: build all the pieces you need, using whatever projects and build systems
they require, then use binman to stitch everything together into an image. It:

- reads an image description from a devicetree and works out what to place
  where, with padding, alignment, compression and hashing;
- supports hierarchical images and a large set of entry types, including FIT,
  CBFS, ARM Trusted Firmware FIP and many SoC-specific formats;
- lets firmware find other binaries in the image, using linker symbols or the
  devicetree description of the image;
- inspects existing images, extracting and replacing their contents and
  repacking where needed;
- copes with missing binary blobs and fetches the external tools it needs.

Binman is designed primarily for use with U-Boot and associated binaries such
as ARM Trusted Firmware, but is general enough to be used with other projects.

Installation
------------

Install the latest release from PyPI::

    pip install binary-manager

The ``pylibfdt`` dependency is built from source, so this needs ``swig``, a C
compiler and the Python development headers (on Debian and Ubuntu:
``apt install swig build-essential python3-dev``).

The ``binman`` command is then on your path.

Quick start
-----------

Build an image from the description in a devicetree, taking the input files
from the current directory::

    binman build -d u-boot.dtb

List the contents of an existing image::

    binman ls -i image.bin

Binman runs external tools for some entry types. To install any which are
missing::

    binman tool -f missing

See ``binman -H`` for the complete manual, or the documentation linked below.

Documentation
-------------

Full documentation is hosted on Read the Docs:

    https://binman.readthedocs.io/

Development
-----------

Run the test suite from a checkout::

    pip install -r requirements.txt
    pip install -e .[test]
    binman tool -f missing
    binman test

The tests build some small x86 ELF programs, so they need ``make`` and a gcc
which can produce 32-bit x86 code (``gcc-multilib``), or set ``CROSS_COMPILE``
to a suitable cross-compiler. They also need a recent ``mkimage`` from U-Boot,
since the expected output tracks its development; pass ``--toolpath`` to point
binman at a U-Boot ``tools/`` build directory. ``binman test -T`` checks that
the tests cover all of the code.

The ``u_boot_pylib`` and ``dtoc`` libraries are vendored from the U-Boot tree,
so no surrounding U-Boot source is required.
