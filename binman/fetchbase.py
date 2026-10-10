# SPDX-License-Identifier: GPL-2.0+
# Copyright 2026 Canonical Ltd
# Written by Simon Glass <simon.glass@canonical.com>
#
"""Common base functionality for fetchable items (bintools and blobs)

This module provides shared infrastructure for bintools and blobs, including:
- Constants for fetch methods and status
- Module discovery and loading
- Building from git repositories
- Fetching from URLs
"""

import glob
import importlib
import multiprocessing
import os
import tempfile

from u_boot_pylib import command
from u_boot_pylib import tools

BINMAN_DIR = os.path.dirname(os.path.realpath(__file__))

# Possible ways of fetching (FETCH_COUNT is number of ways)
FETCH_ANY, FETCH_BIN, FETCH_BUILD, FETCH_COUNT = range(4)

FETCH_NAMES = {
    FETCH_ANY: 'any method',
    FETCH_BIN: 'binary download',
    FETCH_BUILD: 'build from source'
}

# Status of fetching
FETCHED, FAIL, PRESENT, STATUS_COUNT = range(4)

# Environment variables which tell git which repository to use, as listed by
# 'git rev-parse --local-env-vars'. Git sets these when it runs a hook or a
# 'git rebase --exec' command, so a build started from there would otherwise
# use that repository instead of the one being built
GIT_LOCAL_ENV = (
    'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_CONFIG', 'GIT_CONFIG_PARAMETERS',
    'GIT_CONFIG_COUNT', 'GIT_OBJECT_DIRECTORY', 'GIT_DIR', 'GIT_WORK_TREE',
    'GIT_IMPLICIT_WORK_TREE', 'GIT_GRAFT_FILE', 'GIT_INDEX_FILE',
    'GIT_NO_REPLACE_OBJECTS', 'GIT_REPLACE_REF_BASE', 'GIT_PREFIX',
    'GIT_SHALLOW_FILE', 'GIT_COMMON_DIR')


def build_env(env=None):
    """Get the environment to use when building from a git repository

    Args:
        env: Environment variables to add, or None

    Returns:
        dict: The environment, without the variables in GIT_LOCAL_ENV
    """
    base = tools.get_env_with_path() or os.environ
    run_env = {key: val for key, val in base.items()
               if key not in GIT_LOCAL_ENV}
    run_env.update(env or {})
    return run_env


def run_build(*args, env):
    """Run a command to build from source

    This uses command.run_one() since tools.run() does not support setting the
    environment

    Args:
        args: Command and its arguments
        env (dict): Environment to use, from build_env()

    Raises:
        ValueError: The command failed
    """
    result = command.run_one(*args, capture=True, capture_stderr=True,
                             env=env, raise_on_error=False)
    if result.return_code:
        raise ValueError(f"Error {result.return_code} running "
                         f"'{' '.join(args)}': "
                         f"{result.stderr or result.stdout}")


def build_from_git(git_repo, make_targets, output_path, git_branch=None,
                   env=None, make_flags=None, make_path=None):
    """Build a file from a git repository

    This clones the repo in a temporary directory, builds it with 'make',
    then returns the filename of the resulting file.

    Args:
        git_repo: URL of git repo
        make_targets: List of targets to pass to 'make'
        output_path: Relative path of the output file in the repo after build
        git_branch: Branch or tag to check out, or None for default
        env: Environment variables to set for make, or None
        make_flags: Additional flags to pass to make, or None
        make_path: Relative path inside git repo containing the Makefile,
            or None

    Returns:
        tuple:
            str: Path to built file
            str: Temp directory to remove
        or None on error
    """
    run_env = build_env(env)
    tmpdir = tempfile.mkdtemp(prefix='binmanb.')
    print(f"- clone git repo '{git_repo}' to '{tmpdir}'")
    if git_branch:
        run_build('git', 'clone', '--depth', '1', '--branch', git_branch,
                  git_repo, tmpdir, env=run_env)
    else:
        run_build('git', 'clone', '--depth', '1', git_repo, tmpdir,
                  env=run_env)

    for target in make_targets:
        print(f"- build target '{target}'")
        makedir = tmpdir
        if make_path:
            makedir = os.path.join(tmpdir, make_path)
        cmd = ['make', '-C', makedir, '-j', f'{multiprocessing.cpu_count()}',
               target]
        if make_flags:
            cmd += make_flags
        run_build(*cmd, env=run_env)

    fname = os.path.join(tmpdir, output_path)
    if not os.path.exists(fname):
        print(f"- File '{fname}' was not produced")
        return None
    return fname, tmpdir


def fetch_from_url(url, make_executable=False):
    """Fetch a file from a URL

    Args:
        url: URL to fetch from
        make_executable: If True, make the file executable after download

    Returns:
        tuple:
            str: Path to downloaded file
            str: Temp directory to remove, or None
    """
    fname, tmpdir = tools.download(url)
    if make_executable:
        tools.run('chmod', 'a+x', fname)
    return fname, tmpdir


def get_module_list(subdir, include_testing=False):
    """Get a list of modules in a subdirectory

    Args:
        subdir: Subdirectory name relative to BINMAN_DIR (e.g. 'btool', 'blobs')
        include_testing: If True, include '_testing' in the list

    Returns:
        list of str: Sorted list of module names
    """
    files = glob.glob(os.path.join(BINMAN_DIR, subdir, '*.py'))
    names = [os.path.splitext(os.path.basename(fname))[0]
             for fname in files]
    names = [name for name in names
             if name[0] != '_' and name != '__init__']
    # Handle btool_ prefix for modules that conflict with Python libraries
    names = [name[6:] if name.startswith('btool_') else name
             for name in names]
    if include_testing:
        names.append('_testing')
    return sorted(names)


def find_module_class(modules_cache, module_name, package_prefix,
                      class_prefix, fallback_prefix=None):
    """Find and load a class from a module

    Args:
        modules_cache: Dict to cache loaded modules (modified in place)
        module_name: Name of the module to load (e.g. 'mkimage', 'atf')
        package_prefix: Package path prefix (e.g. 'binman.btool', 'binman.blobs')
        class_prefix: Prefix for the class name (e.g. 'Bintool', 'Blob')
        fallback_prefix: If set, try this module name prefix if the first
            import fails (e.g. 'btool_' for bintools)

    Returns:
        The class object if found, else a tuple:
            module name that could not be found
            exception received
    """
    # Convert something like 'u-boot' to 'u_boot'
    module_key = module_name.replace('-', '_')
    module = modules_cache.get(module_key)
    class_name = f'{class_prefix}{module_key}'

    # Import the module if we have not already done so
    if not module:
        try:
            module = importlib.import_module(f'{package_prefix}.{module_key}')
        except ImportError as exc:
            if fallback_prefix:
                try:
                    # Deal with classes which must be renamed due to conflicts
                    # with Python libraries
                    module = importlib.import_module(
                        f'{package_prefix}.{fallback_prefix}{module_key}')
                except ImportError:
                    return module_key, exc
            else:
                return module_key, exc
        modules_cache[module_key] = module

    # Look up the expected class name
    return getattr(module, class_name)
