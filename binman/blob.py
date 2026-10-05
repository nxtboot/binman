# SPDX-License-Identifier: GPL-2.0+
# Copyright 2026 Canonical Ltd
# Written by Simon Glass <simon.glass@canonical.com>
#
"""Base class for all blob handlers

This defines the common functionality for all blob handlers, including
caching, fetching from various sources, and building from source.
"""

import os
import shutil

from binman import blobstore
from binman import fetchbase

from u_boot_pylib import terminal
from u_boot_pylib import tools

# Format string for listing blobs
FORMAT = '%-30.30s %-40.40s %s'

# List of known modules, to avoid importing the module multiple times
modules = {}

# Priorities for different fetch sources
PRIORITY_BUILD = 10    # Building from source (highest priority - open source)
PRIORITY_LOCAL = 20    # Local directories
PRIORITY_URL = 50      # URL downloads (lowest priority)


class Blob:
    """Handler for firmware blobs that can be fetched or built

    This is the base class for all blob handlers. Each handler corresponds to
    a specific firmware blob type identified by its compatible string.

    Attributes:
        compatible: Compatible string identifying this blob type
        desc: Description of the blob
    """
    # Directory to store blobs. Must be set by set_blob_dir() before use.
    blobdir = ''

    def __init__(self, compatible, desc):
        """Create a new Blob handler

        Args:
            compatible: Compatible string (e.g. 'arm,trusted-firmware-a')
            desc: Description of this blob type
        """
        self.compatible = compatible
        self.desc = desc

    @staticmethod
    def find_blob_class(compatible):
        """Look up the blob class for a compatible string

        Args:
            compatible: Compatible string to look up, e.g. 'arm,trusted-firmware-a'

        Returns:
            The blob class object if found, else a tuple:
                module name that could not be found
                exception received
        """
        # Convert compatible like 'arm,trusted-firmware-a' to module name 'atf'
        # This requires looking up the mapping in blobstores.yaml
        handler_name = blobstore.get_handler_for_compatible(compatible)
        if not handler_name:
            return compatible, ImportError(f"No handler for '{compatible}'")

        return fetchbase.find_module_class(
            modules, handler_name, 'binman.blobs', 'Blob')

    @staticmethod
    def create(compatible):
        """Create a new blob handler object

        Args:
            compatible: Compatible string, e.g. 'arm,trusted-firmware-a'

        Returns:
            A new object of the correct type (a subclass of Blob)
        """
        cls = Blob.find_blob_class(compatible)
        if isinstance(cls, tuple):
            raise ValueError("Cannot import blob module '%s': %s" % cls)

        # Call its constructor to get the object we want
        obj = cls(compatible)
        return obj

    @classmethod
    def set_blob_dir(cls, pathname):
        """Set the path to use to store and find blobs"""
        cls.blobdir = pathname

    @staticmethod
    def get_blob_list(include_testing=False):
        """Get a list of the known blob handlers

        Returns:
            list of str: names of all blob handlers known to binman
        """
        return fetchbase.get_module_list('blobs', include_testing)

    def get_cache_path(self, version, arch, plat, filename):
        """Get the cache path for a blob

        Args:
            version: Version string (e.g. '2.9')
            arch: Architecture (e.g. 'aarch64')
            plat: Platform (e.g. 'sun50i_a64')
            filename: Filename of the blob

        Returns:
            str: Full path to the cached blob file
        """
        return os.path.join(self.blobdir, self.compatible, version, arch, plat,
                           filename)

    def is_cached(self, version, arch, plat, filename):
        """Check if a blob is already cached

        Args:
            version: Version string
            arch: Architecture
            plat: Platform
            filename: Filename of the blob

        Returns:
            bool: True if the blob is already cached
        """
        path = self.get_cache_path(version, arch, plat, filename)
        return os.path.exists(path)

    def add_to_cache(self, filepath, version, arch, plat, filename):
        """Add a blob file to the cache

        Args:
            filepath: Path to the file to add
            version: Version string
            arch: Architecture
            plat: Platform
            filename: Target filename in cache

        Returns:
            str: Path where the file was cached
        """
        cache_path = self.get_cache_path(version, arch, plat, filename)
        cache_dir = os.path.dirname(cache_path)
        os.makedirs(cache_dir, exist_ok=True)
        shutil.copy2(filepath, cache_path)
        return cache_path

    def fetch(self, version, arch, plat, source_only=False, no_source=False):
        """Fetch a blob using available methods

        This tries to fetch the blob using all available methods in priority
        order: build from source (priority 10), local (20), URL download (50).

        Args:
            version: Version string to fetch
            arch: Target architecture
            plat: Target platform
            source_only: Only try building from source
            no_source: Don't try building from source

        Returns:
            tuple:
                str: Path to the fetched file
                str: Temp directory to clean up, or None
            or None if fetch failed
        """
        # Try build first if not disabled (highest priority)
        if not no_source:
            # Subclasses which can build override build()
            # pylint: disable-next=assignment-from-none
            result = self.build(version, arch, plat)
            if result:
                return result
            if source_only:
                return None

        # Try stores in priority order. Building from source is dealt with
        # above, so skip any build stores, which would only repeat the build,
        # or build when asked not to
        stores = blobstore.get_stores_for_compatible(self.compatible)
        for store in sorted(stores, key=lambda s: s.priority):
            if store.store_type == 'build':
                continue
            result = store.fetch(self.compatible, version, arch, plat)
            if result:
                return result

        return None

    def build(self, version, arch, plat):
        """Build the blob from source

        This should be overridden by subclasses that support building from
        source.

        Args:
            version: Version string to build
            arch: Target architecture
            plat: Target platform

        Returns:
            tuple:
                str: Path to the built file
                str: Temp directory to clean up, or None
            or None if build is not supported
        """
        return None

    @classmethod
    def build_from_git(cls, git_repo, make_targets, output_path, git_branch=None,
                       env=None, make_flags=None):
        """Build a blob from a git repository

        This clones the repo in a temporary directory, builds it with 'make',
        then returns the filename of the resulting blob.

        Args:
            git_repo: URL of git repo
            make_targets: List of targets to pass to 'make'
            output_path: Relative path of the output file in the repo after build
            git_branch: Branch or tag to check out, or None for default
            env: Environment variables to set for make, or None
            make_flags: Additional flags to pass to make, or None

        Returns:
            tuple:
                str: Path to built file
                str: Temp directory to remove
            or None on error
        """
        return fetchbase.build_from_git(
            git_repo, make_targets, output_path, git_branch=git_branch,
            env=env, make_flags=make_flags)

    @classmethod
    def fetch_from_url(cls, url):
        """Fetch a blob from a URL

        Args:
            url: URL to fetch from

        Returns:
            tuple:
                str: Path to downloaded file
                str: Temp directory to remove, or None
        """
        return fetchbase.fetch_from_url(url)

    @staticmethod
    def list_all():
        """List all the blob handlers known to binman"""
        print(FORMAT % ('Compatible', 'Description', 'Handler'))
        print(FORMAT % ('-' * 29, '-' * 39, '-' * 20))

        blobs_info = blobstore.get_all_blobs()
        for compatible, info in sorted(blobs_info.items()):
            print(FORMAT % (compatible, info.get('desc', ''),
                           info.get('handler', '')))

    @staticmethod
    def list_stores():
        """List all blob stores"""
        blobstore.list_stores()

    @staticmethod
    def show_info(compatible):
        """Show detailed information about a blob

        Args:
            compatible: Compatible string to show info for
        """
        info = blobstore.get_blob_info(compatible)
        if not info:
            print(f"Unknown blob: {compatible}")
            return

        print(f"Compatible: {compatible}")
        print(f"Description: {info.get('desc', 'N/A')}")
        print(f"Handler: {info.get('handler', 'N/A')}")

        stores = info.get('stores', [])
        if stores:
            print("Stores:")
            for store in stores:
                pattern = store.get('pattern')
                print(f"  - {store.get('store', 'unknown')}" +
                      (f': {pattern}' if pattern else ''))

    @staticmethod
    def fetch_blobs(compatibles, version=None, arch=None, plat=None,
                   source_only=False, no_source=False):
        """Fetch one or more blobs

        Args:
            compatibles: List of compatible strings to fetch
            version: Version to fetch (required)
            arch: Target architecture (required)
            plat: Target platform (required)
            source_only: Only try building from source
            no_source: Don't try building from source

        Returns:
            bool: True on success, False on failure
        """
        col = terminal.Color()
        failed = []

        for compatible in compatibles:
            print(col.build(col.YELLOW, f'Fetch: {compatible}'))
            try:
                blob = Blob.create(compatible)
                result = blob.fetch(version, arch, plat, source_only, no_source)
                if result:
                    fname, tmpdir = result
                    # Add to cache
                    filename = os.path.basename(fname)
                    cache_path = blob.add_to_cache(fname, version, arch, plat,
                                                   filename)
                    print(f"- cached to '{cache_path}'")
                    if tmpdir:
                        shutil.rmtree(tmpdir)
                else:
                    print(col.build(col.RED, f'- failed to fetch'))
                    failed.append(compatible)
            except Exception as exc:
                print(col.build(col.RED, f'- error: {exc}'))
                failed.append(compatible)

        if failed:
            print(col.build(col.RED, f'Failed: {" ".join(failed)}'))
            return False
        return True

    @staticmethod
    def add_blob(compatible, filepath, version, arch, plat):
        """Manually add a blob to the cache

        Args:
            compatible: Compatible string for the blob
            filepath: Path to the file to add
            version: Version string
            arch: Architecture
            plat: Platform

        Returns:
            str: Path where the file was cached
        """
        if not os.path.exists(filepath):
            raise ValueError(f"File not found: {filepath}")

        # Create a minimal blob object just for caching
        blob = Blob(compatible, '')
        filename = os.path.basename(filepath)
        cache_path = blob.add_to_cache(filepath, version, arch, plat, filename)
        print(f"Added '{filepath}' to cache as '{cache_path}'")
        return cache_path
