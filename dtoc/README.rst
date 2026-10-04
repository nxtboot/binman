.. SPDX-License-Identifier: GPL-2.0+

Devicetree library (vendored from dtoc)
=======================================

This is the devicetree access library from U-Boot's dtoc tool, providing the
``fdt`` and ``fdt_util`` modules which binman uses to read and update
devicetree files.

Only these library modules are included here. The dtoc devicetree-to-C
generator itself, along with its tests, remains in the U-Boot tree.
