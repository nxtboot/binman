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

import fcntl
import glob
import hashlib
import importlib
import multiprocessing
import os
import tempfile

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
    run_env = {key: val for key, val in os.environ.items()
               if key not in GIT_LOCAL_ENV}
    run_env.update(env or {})
    return run_env


def run_build(*args, env):
    """Run a command to build from source

    Args:
        args: Command and its arguments
        env (dict): Environment to use, from build_env(). Any tool paths are
            added to its PATH

    Raises:
        ValueError: The command failed
    """
    tools.run(*args, env=env)


def _make(srcdir, make_targets, output_path, run_env, make_flags, make_path):
    """Build a file from source with 'make'

    Args:
        srcdir: Directory containing the source
        make_targets: List of targets to pass to 'make'
        output_path: Relative path of the output file in srcdir after build
        run_env: Environment to use for make, from build_env()
        make_flags: Additional flags to pass to make, or None
        make_path: Relative path inside srcdir containing the Makefile, or
            None

    Returns:
        str: Path to built file, or None if it was not produced
    """
    for target in make_targets:
        print(f"- build target '{target}'")
        makedir = srcdir
        if make_path:
            makedir = os.path.join(srcdir, make_path)
        cmd = ['make', '-C', makedir, '-j', f'{multiprocessing.cpu_count()}',
               target]
        if make_flags:
            cmd += make_flags
        run_build(*cmd, env=run_env)

    fname = os.path.join(srcdir, output_path)
    if not os.path.exists(fname):
        print(f"- File '{fname}' was not produced")
        return None
    return fname


def get_repo_dir(workdir, git_repo):
    """Get the directory in which to build from a git repository

    The directory is named after the repository, with part of a hash of its
    URL so that repositories with the same name do not clash.

    Args:
        workdir: Directory holding the builds
        git_repo: URL of git repo

    Returns:
        str: Path to the directory, e.g. <workdir>/trusted-firmware-a-1234abcd
    """
    name = os.path.basename(git_repo.rstrip('/')).removesuffix('.git')
    digest = hashlib.sha256(git_repo.encode('utf-8')).hexdigest()[:8]
    return os.path.join(workdir, f'{name}-{digest}')


def _checkout(repodir, git_repo, git_branch, run_env):
    """Get a working tree for a version of a git repository

    The repository is fetched into the 'src' subdirectory, with a working tree
    for each branch or tag. An existing working tree is used as is, so that a
    build can carry on from where it left off.

    Args:
        repodir: Directory for the repository, from get_repo_dir()
        git_repo: URL of git repo
        git_branch: Branch or tag to check out, or None for default
        run_env: Environment to use for git, from build_env()

    Returns:
        str: Path to the working tree
    """
    ref = git_branch or 'HEAD'
    tree = os.path.join(repodir, ref.replace('/', '_'))
    if os.path.exists(tree):
        print(f"- use existing tree '{tree}'")
        return tree

    srcdir = os.path.join(repodir, 'src')
    if not os.path.exists(srcdir):
        run_build('git', 'init', '-q', '--bare', srcdir, env=run_env)
    print(f"- fetch '{ref}' from git repo '{git_repo}' to '{tree}'")
    run_build('git', '-C', srcdir, 'fetch', '-q', '--depth', '1', git_repo,
              ref, env=run_env)

    # Drop any working tree which has been deleted, so it can be added again
    run_build('git', '-C', srcdir, 'worktree', 'prune', env=run_env)
    run_build('git', '-C', srcdir, 'worktree', 'add', '-q', '--detach', tree,
              'FETCH_HEAD', env=run_env)
    return tree


def build_from_git(git_repo, make_targets, output_path, git_branch=None,
                   env=None, make_flags=None, make_path=None, workdir=None):
    """Build a file from a git repository

    This checks out the repo, builds it with 'make', then returns the filename
    of the resulting file.

    With a work directory, the repo is checked out there and kept, so that a
    later build of the same version can reuse it, and a failed build can be
    examined. Otherwise the repo is cloned into a temporary directory, which
    the caller must remove.

    Args:
        git_repo: URL of git repo
        make_targets: List of targets to pass to 'make'
        output_path: Relative path of the output file in the repo after build
        git_branch: Branch or tag to check out, or None for default
        env: Environment variables to set for make, or None
        make_flags: Additional flags to pass to make, or None
        make_path: Relative path inside git repo containing the Makefile,
            or None
        workdir: Directory to build in, or None to use a temporary directory

    Returns:
        tuple:
            str: Path to built file
            str: Temp directory to remove, or None if there is none
        or None on error
    """
    run_env = build_env(env)
    if not workdir:
        tmpdir = tempfile.mkdtemp(prefix='binmanb.')
        print(f"- clone git repo '{git_repo}' to '{tmpdir}'")
        if git_branch:
            run_build('git', 'clone', '--depth', '1', '--branch', git_branch,
                      git_repo, tmpdir, env=run_env)
        else:
            run_build('git', 'clone', '--depth', '1', git_repo, tmpdir,
                      env=run_env)
        fname = _make(tmpdir, make_targets, output_path, run_env, make_flags,
                      make_path)
        return (fname, tmpdir) if fname else None

    # Git runs in the repository, so needs an absolute path to the tree
    repodir = get_repo_dir(os.path.abspath(workdir), git_repo)
    os.makedirs(repodir, exist_ok=True)

    # Only one build can use the repository at a time
    with open(os.path.join(repodir, 'lock'), 'w', encoding='utf-8') as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        tree = _checkout(repodir, git_repo, git_branch, run_env)
        try:
            fname = _make(tree, make_targets, output_path, run_env,
                          make_flags, make_path)
        except ValueError:
            print(f"- build failed: see '{tree}'")
            raise
    if not fname:
        print(f"- build left in '{tree}'")
        return None
    return fname, None


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
