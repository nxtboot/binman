# SPDX-License-Identifier: GPL-2.0+
# Copyright 2026 Canonical Ltd
# Written by Simon Glass <simon.glass@canonical.com>
#
"""ARM Trusted Firmware-A (TF-A / ATF) blob handler

This handler supports building TF-A from source for various platforms.
"""

import os

from binman import blob


# Platform-specific build configurations
# Maps platform name to (PLAT value, additional make flags)
PLATFORM_CONFIG = {
    # Allwinner platforms
    'sun50i_a64': ('sun50i_a64', []),
    'sun50i_h5': ('sun50i_a64', []),
    'sun50i_h6': ('sun50i_h6', []),
    'sun50i_h616': ('sun50i_h616', []),

    # Rockchip platforms
    'rk3399': ('rk3399', []),
    'rk3368': ('rk3368', []),
    'rk3328': ('rk3328', []),
    'rk3566': ('rk3568', []),
    'rk3568': ('rk3568', []),
    'rk3588': ('rk3588', []),

    # Generic platform for testing
    'generic': ('fvp', []),
}

# Git repository for TF-A
TF_A_REPO = 'https://github.com/ARM-software/arm-trusted-firmware.git'


class Blobatf(blob.Blob):
    """Handler for ARM Trusted Firmware-A blobs

    This handler can build TF-A from source for supported platforms.
    The resulting BL31 binary is used as the secure firmware on ARM64 systems.
    """

    def __init__(self, compatible):
        super().__init__(compatible, 'ARM Trusted Firmware-A (BL31)')

    def build(self, version, arch, plat):
        """Build TF-A from source

        Args:
            version: Version/tag to build (e.g. '2.9', 'lts-v2.10.4')
            arch: Target architecture (must be 'aarch64')
            plat: Target platform (e.g. 'sun50i_a64', 'rk3399')

        Returns:
            tuple: (path to bl31.bin, temp directory) or None on failure
        """
        if arch != 'aarch64':
            print(f"- TF-A only supports aarch64, not '{arch}'")
            return None

        if plat not in PLATFORM_CONFIG:
            print(f"- Unknown platform '{plat}' for TF-A")
            print(f"- Supported platforms: {', '.join(sorted(PLATFORM_CONFIG))}")
            return None

        tf_plat, extra_flags = PLATFORM_CONFIG[plat]

        # Determine git branch/tag
        if version.startswith('lts-'):
            git_branch = version
        elif version.startswith('v'):
            git_branch = version
        else:
            git_branch = f'v{version}'

        # Build environment, using the user's toolchain if they have set one
        env = {
            'CROSS_COMPILE': os.environ.get('CROSS_COMPILE',
                                            'aarch64-linux-gnu-'),
        }

        # Make flags
        make_flags = [
            f'PLAT={tf_plat}',
            'DEBUG=0',
        ] + extra_flags

        # Output path for BL31
        output_path = f'build/{tf_plat}/release/bl31.bin'

        print(f"- Building TF-A {git_branch} for {tf_plat}")
        # Build just BL31, since other images, such as the Cortex-M0 firmware
        # on rk3399, need other toolchains
        return self.build_from_git(
            TF_A_REPO,
            make_targets=['bl31'],
            output_path=output_path,
            git_branch=git_branch,
            env=env,
            make_flags=make_flags
        )
