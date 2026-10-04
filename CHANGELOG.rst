Changelog
=========

All notable changes to this project are documented here. The format is
based on `Keep a Changelog <https://keepachangelog.com/en/1.1.0/>`_ and
the project follows `Semantic Versioning <https://semver.org/>`_.

Unreleased
----------

Fixed
~~~~~
- The vendored ``u_boot_pylib`` and ``dtoc`` libraries are installed inside
  the ``binman`` package rather than as top-level packages. These shadowed
  U-Boot's own copies, breaking its dtoc tool when binman was installed in
  the same environment, and clashed with the separate ``u_boot_pylib`` and
  ``dtoc`` packages.

0.1.0 - 2026-10-04
------------------

Changed
~~~~~~~
- Binman is now developed in its own repository at
  https://github.com/nxtboot/binman, with its history carried over from
  the U-Boot tree.
- Binman is distributed as the self-contained ``binary-manager`` package,
  with ``u_boot_pylib`` and the ``dtoc`` devicetree library vendored in,
  installable from PyPI with ``pip install binary-manager``. Its Python
  dependencies are now declared, so it no longer needs them to be installed
  separately.
- ``binman -V`` shows the version of the installed package.
- Documentation is now published at https://binman.readthedocs.io/.

Fixed
~~~~~
- ``binman tool -f fiptool`` finds the tool where current TF-A builds it,
  in ``build/fvp/release/tools/fiptool/``, instead of reporting that it was
  not produced.

Earlier releases
----------------

Releases 0.0.7 and earlier were published from the U-Boot tree and predate
this changelog.
