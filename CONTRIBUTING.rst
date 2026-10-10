Contributing to Binman
======================

Development setup
-----------------

Work in a virtual environment::

    python -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt
    pip install -e .[test]

Installing ``pylibfdt`` builds it from source, which needs ``swig``, a C
compiler and the Python development headers.

Running the tests
-----------------

The tests need a few tools:

- ``make`` and a gcc which can produce 32-bit x86 code (``gcc-multilib``),
  to build some small ELF test programs. On other hosts, set
  ``CROSS_COMPILE`` to a suitable cross-compiler.
- ``dtc``, the devicetree compiler.
- A recent ``mkimage`` and the other U-Boot host tools, since some tests
  check their exact output. Build these from U-Boot (``make
  tools-only_defconfig tools-only``) and pass the ``tools/`` directory with
  ``--toolpath``. The CI uses the U-Boot commit given by ``UBOOT_REF`` in
  ``.github/workflows/test.yml``.
- The other external tools which binman runs, which it can fetch itself::

    binman tool -f missing

Tests which need a missing tool are skipped. Then::

    binman --toolpath <u-boot-build>/tools test             # the whole suite
    binman --toolpath <u-boot-build>/tools test <name>      # one test
    binman --toolpath <u-boot-build>/tools test -T          # check coverage

The coverage check requires every line of binman to be covered by the
tests. See ``doc/binman_tests.rst`` for how to write tests.

Building the documentation
--------------------------

::

    pip install -r doc/requirements.txt
    make -C doc html        # output in doc/_build/html

The manual itself lives in ``binman/binman.rst`` and the entry-type and
bintool references are generated from the docstrings in ``binman/etype/`` and
``binman/btool/``. ``doc/`` only wraps these for Sphinx, so edit the manual
and docstrings there.

Building the package
--------------------

::

    python -m build
    twine check --strict dist/*

Vendored code
-------------

Some code is copied from the U-Boot tree, so that the project is
self-contained:

- ``binman/_vendor/dtoc/``: the ``fdt`` and ``fdt_util`` devicetree modules
  from dtoc
- ``binman/test/include/``: the headers used by the ELF test programs
  (``linux/build_bug.h`` is a minimal stand-in)
- ``doc/binman_docs.py`` and ``doc/binman_tests.rst``

The vendored library lives inside the ``binman`` package, rather than at the
top level, so that installing binman does not clash with U-Boot's own copy or
with the separate ``dtoc`` package. ``binman/__init__.py`` adds
``binman/_vendor/`` to the start of the import path, so the code still imports
it by its usual name and matches the U-Boot tree.

The U-Boot Python library is not vendored: it is a dependency, from the
``u-boot-pylib`` package (https://github.com/nxtboot/u-boot-pylib).

When refreshing these from U-Boot, note the U-Boot commit in the commit
message.

Continuous integration
----------------------

The *Tests* workflow builds the U-Boot host tools, runs the suite on Python
3.10-3.12, checks test coverage and builds and checks the package on every
push and pull request.

Making a release
----------------

Releases are published to PyPI automatically by the *Release* workflow
when a version tag is pushed. The flow is:

1. Update ``CHANGELOG.rst``: move the ``Unreleased`` entries under a new
   ``X.Y.Z - <date>`` heading.
2. Bump ``version`` in ``pyproject.toml``.
3. Commit the changes.
4. Tag it. The tag must be ``v`` followed by the exact version, for
   example::

       git tag v0.1.0
       git push origin v0.1.0

   A tag containing ``rc`` (for example ``v0.1.0rc1``) publishes to
   TestPyPI; a final tag publishes to the real PyPI. The workflow
   refuses to publish if the tag does not match the project version.

   You can also trigger the *Release* workflow manually (the
   ``workflow_dispatch`` option) to publish the current branch to
   TestPyPI for a dry run, without a tag.

Publishing uses PyPI Trusted Publishing (OIDC), so no API tokens are
stored. The PyPI and TestPyPI projects must each be configured to trust
this repository's ``release.yml`` workflow (environments ``pypi`` and
``testpypi``) before the first release.
