Changelog
=========

All notable changes to this project are documented here. The format is
based on `Keep a Changelog <https://keepachangelog.com/en/1.1.0/>`_ and
the project follows `Semantic Versioning <https://semver.org/>`_.

Unreleased
----------

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

Earlier releases
----------------

Releases 0.0.7 and earlier were published from the U-Boot tree and predate
this changelog.
