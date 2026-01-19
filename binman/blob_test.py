# SPDX-License-Identifier: GPL-2.0+
# Copyright 2026 Canonical Ltd
# Written by Simon Glass <simon.glass@canonical.com>
#
"""Tests for the Blob class"""

import os
import shutil
import tempfile
import unittest
import unittest.mock

from binman import blob
from binman import blobstore
from binman.blob import Blob

from u_boot_pylib import command
from u_boot_pylib import terminal
from u_boot_pylib import tools


# pylint: disable=R0904
class TestBlob(unittest.TestCase):
    """Tests for the Blob class"""

    def setUp(self):
        """Set up test fixtures"""
        self._indir = tempfile.mkdtemp(prefix='blobtest.')
        Blob.set_blob_dir(self._indir)
        # Clear the config cache for each test
        blobstore._config = None

    def tearDown(self):
        """Clean up test fixtures"""
        if self._indir:
            shutil.rmtree(self._indir)
        self._indir = None

    def test_cache_path(self):
        """Test that cache paths are constructed correctly"""
        b = Blob('test,blob', 'test blob')
        path = b.get_cache_path('1.0', 'aarch64', 'sun50i', 'bl31.bin')
        expected = os.path.join(self._indir, 'test,blob', '1.0', 'aarch64',
                               'sun50i', 'bl31.bin')
        self.assertEqual(expected, path)

    def test_is_cached_not_exists(self):
        """Test is_cached returns False when file does not exist"""
        b = Blob('test,blob', 'test blob')
        self.assertFalse(b.is_cached('1.0', 'aarch64', 'sun50i', 'bl31.bin'))

    def test_is_cached_exists(self):
        """Test is_cached returns True when file exists"""
        b = Blob('test,blob', 'test blob')
        # Create the cached file
        cache_path = b.get_cache_path('1.0', 'aarch64', 'sun50i', 'bl31.bin')
        os.makedirs(os.path.dirname(cache_path))
        tools.write_file(cache_path, b'test content')
        self.assertTrue(b.is_cached('1.0', 'aarch64', 'sun50i', 'bl31.bin'))

    def test_add_to_cache(self):
        """Test adding a file to the cache"""
        b = Blob('test,blob', 'test blob')
        # Create a source file
        src_file = os.path.join(self._indir, 'source.bin')
        tools.write_file(src_file, b'blob content')

        cache_path = b.add_to_cache(src_file, '2.0', 'arm', 'generic',
                                    'firmware.bin')
        self.assertTrue(os.path.exists(cache_path))
        self.assertEqual(b'blob content', tools.read_file(cache_path))

    def test_pattern_substitution(self):
        """Test pattern substitution in stores"""
        pattern = 'blobs/{version}/{arch}/{plat}/bl31.bin'
        result = blobstore.BlobStore.substitute_pattern(
            pattern, '2.9', 'aarch64', 'sun50i_a64')
        self.assertEqual('blobs/2.9/aarch64/sun50i_a64/bl31.bin', result)

    def test_pattern_substitution_partial(self):
        """Test pattern substitution with some values missing"""
        pattern = 'blobs/{version}/{arch}/firmware.bin'
        result = blobstore.BlobStore.substitute_pattern(
            pattern, '1.0', 'aarch64', None)
        self.assertEqual('blobs/1.0/aarch64/firmware.bin', result)

    def test_local_store_fetch_exists(self):
        """Test LocalBlobStore finding an existing file"""
        # Create the file
        test_dir = os.path.join(self._indir, 'local')
        os.makedirs(test_dir)
        test_file = os.path.join(test_dir, 'blob.bin')
        tools.write_file(test_file, b'local blob')

        store = blobstore.LocalBlobStore('test', 20, 'test store',
                                         os.path.join(test_dir, 'blob.bin'))
        result = store.fetch('test,blob', '1.0', 'aarch64', 'generic')
        self.assertIsNotNone(result)
        self.assertEqual(test_file, result[0])
        self.assertIsNone(result[1])

    def test_local_store_fetch_not_exists(self):
        """Test LocalBlobStore when file does not exist"""
        store = blobstore.LocalBlobStore('test', 20, 'test store',
                                         '/nonexistent/path/blob.bin')
        result = store.fetch('test,blob', '1.0', 'aarch64', 'generic')
        self.assertIsNone(result)

    def test_get_blob_list(self):
        """Test listing blob handlers"""
        handlers = Blob.get_blob_list()
        # Should be a list (may be empty in test environment)
        self.assertIsInstance(handlers, list)

    def test_get_blob_list_with_testing(self):
        """Test listing blob handlers including testing handler"""
        handlers = Blob.get_blob_list(include_testing=True)
        self.assertIn('_testing', handlers)

    def test_create_store_local(self):
        """Test creating a local store"""
        store = blobstore.create_store('test', 'local', 20, 'desc',
                                       '/path/to/blob', {})
        self.assertIsInstance(store, blobstore.LocalBlobStore)
        self.assertEqual('local', store.store_type)
        self.assertEqual(20, store.priority)

    def test_create_store_url(self):
        """Test creating a URL store"""
        store = blobstore.create_store('test', 'url', 50, 'desc',
                                       'https://example.com/blob', {})
        self.assertIsInstance(store, blobstore.UrlBlobStore)
        self.assertEqual('url', store.store_type)

    def test_create_store_build(self):
        """Test creating a build store"""
        store = blobstore.create_store('test', 'build', 10, 'desc', '', {})
        self.assertIsInstance(store, blobstore.BuildBlobStore)
        self.assertEqual('build', store.store_type)

    def test_create_store_unknown(self):
        """Test creating an unknown store type returns None"""
        store = blobstore.create_store('test', 'unknown', 50, 'desc', '', {})
        self.assertIsNone(store)

    def test_add_blob_static(self):
        """Test the static add_blob method"""
        # Create a source file
        src_file = os.path.join(self._indir, 'add_test.bin')
        tools.write_file(src_file, b'added blob')

        with terminal.capture() as (stdout, _):
            cache_path = Blob.add_blob('added,blob', src_file, '1.0',
                                       'aarch64', 'generic')

        self.assertTrue(os.path.exists(cache_path))
        self.assertIn('Added', stdout.getvalue())

    def test_add_blob_file_not_found(self):
        """Test add_blob raises error for missing file"""
        with self.assertRaises(ValueError) as exc:
            Blob.add_blob('test,blob', '/nonexistent/file.bin', '1.0',
                         'aarch64', 'generic')
        self.assertIn('File not found', str(exc.exception))


class TestBlobFunctional(unittest.TestCase):
    """Functional tests for blob fetching with mocked network operations"""

    def setUp(self):
        """Set up test fixtures"""
        self._indir = tempfile.mkdtemp(prefix='blobfunc.')
        Blob.set_blob_dir(self._indir)
        blobstore._config = None

    def tearDown(self):
        """Clean up test fixtures"""
        if self._indir:
            shutil.rmtree(self._indir)
        self._indir = None
        blobstore._config = None

    def test_testing_handler_build(self):
        """Test the _testing handler's build method"""
        from binman.blobs._testing import Blob_testing

        handler = Blob_testing('test,testing')
        result = handler.build('1.0', 'aarch64', 'generic')

        self.assertIsNotNone(result)
        fname, tmpdir = result
        self.assertTrue(os.path.exists(fname))
        self.assertEqual(b'test blob content', tools.read_file(fname))

        # Clean up
        shutil.rmtree(tmpdir)

    def test_testing_handler_build_custom_result(self):
        """Test the _testing handler with custom build result"""
        from binman.blobs._testing import Blob_testing

        handler = Blob_testing('test,testing')
        handler.build_result = None  # Explicitly set to None to use default

        # Now test with a custom result
        custom_file = os.path.join(self._indir, 'custom.bin')
        tools.write_file(custom_file, b'custom content')
        handler.build_result = (custom_file, None)

        result = handler.build('1.0', 'aarch64', 'generic')
        self.assertEqual(custom_file, result[0])
        self.assertIsNone(result[1])

    def test_atf_handler_wrong_arch(self):
        """Test ATF handler rejects non-aarch64 architectures"""
        from binman.blobs.atf import Blobatf

        handler = Blobatf('arm,trusted-firmware-a')
        with terminal.capture() as (stdout, _):
            result = handler.build('2.9', 'arm', 'sun50i_a64')

        self.assertIsNone(result)
        self.assertIn('only supports aarch64', stdout.getvalue())

    def test_atf_handler_unknown_platform(self):
        """Test ATF handler rejects unknown platforms"""
        from binman.blobs.atf import Blobatf

        handler = Blobatf('arm,trusted-firmware-a')
        with terminal.capture() as (stdout, _):
            result = handler.build('2.9', 'aarch64', 'unknown_platform')

        self.assertIsNone(result)
        self.assertIn('Unknown platform', stdout.getvalue())

    def test_atf_handler_build_with_mock(self):
        """Test ATF handler build with mocked git and make"""
        from binman.blobs.atf import Blobatf

        handler = Blobatf('arm,trusted-firmware-a')
        result_tmpdir = [None]

        def handle_command(pipe_list):
            cmd = pipe_list[0]
            # Handle git clone
            if cmd[0] == 'git':
                tmpdir = cmd[-1]
                result_tmpdir[0] = tmpdir
                os.makedirs(tmpdir, exist_ok=True)
            # Handle make - create the output file
            elif cmd[0] == 'make':
                # Find tmpdir from -C flag
                tmpdir = cmd[2]
                output_dir = os.path.join(tmpdir, 'build', 'sun50i_a64', 'release')
                os.makedirs(output_dir, exist_ok=True)
                tools.write_file(os.path.join(output_dir, 'bl31.bin'),
                                b'fake bl31 content')
            return command.CommandResult()

        try:
            command.TEST_RESULT = handle_command
            with terminal.capture() as (stdout, _):
                result = handler.build('2.9', 'aarch64', 'sun50i_a64')

            self.assertIsNotNone(result)
            fname, tmpdir = result
            self.assertTrue(os.path.exists(fname))
            self.assertEqual(b'fake bl31 content', tools.read_file(fname))
            self.assertIn('Building TF-A', stdout.getvalue())

            # Clean up
            shutil.rmtree(tmpdir)
        finally:
            command.TEST_RESULT = None

    def test_atf_handler_version_formats(self):
        """Test ATF handler handles different version formats"""
        from binman.blobs.atf import Blobatf

        handler = Blobatf('arm,trusted-firmware-a')
        git_branches = []

        def capture_git(pipe_list):
            cmd = pipe_list[0]
            if cmd[0] == 'git' and 'clone' in cmd:
                # Find --branch argument
                for i, arg in enumerate(cmd):
                    if arg == '--branch':
                        git_branches.append(cmd[i + 1])
                tmpdir = cmd[-1]
                os.makedirs(tmpdir, exist_ok=True)
            elif cmd[0] == 'make':
                tmpdir = cmd[2]
                output_dir = os.path.join(tmpdir, 'build', 'sun50i_a64', 'release')
                os.makedirs(output_dir, exist_ok=True)
                tools.write_file(os.path.join(output_dir, 'bl31.bin'), b'bl31')
            return command.CommandResult()

        try:
            command.TEST_RESULT = capture_git
            with terminal.capture():
                # Test plain version
                result = handler.build('2.9', 'aarch64', 'sun50i_a64')
                if result:
                    shutil.rmtree(result[1])

                # Test v-prefixed version
                result = handler.build('v2.10', 'aarch64', 'sun50i_a64')
                if result:
                    shutil.rmtree(result[1])

                # Test lts version
                result = handler.build('lts-v2.10.4', 'aarch64', 'sun50i_a64')
                if result:
                    shutil.rmtree(result[1])

            self.assertEqual(['v2.9', 'v2.10', 'lts-v2.10.4'], git_branches)
        finally:
            command.TEST_RESULT = None

    def test_url_store_fetch_with_mock(self):
        """Test UrlBlobStore with mocked download"""
        download_file = os.path.join(self._indir, 'downloaded.bin')
        tools.write_file(download_file, b'downloaded content')

        def fake_download(url):
            return download_file, None

        store = blobstore.UrlBlobStore(
            'test-store', 50, 'test',
            'https://example.com/{version}/{arch}/blob.bin', {})

        with unittest.mock.patch.object(tools, 'download',
                                        side_effect=fake_download):
            result = store.fetch('test,blob', '1.0', 'aarch64', 'generic')

        self.assertIsNotNone(result)
        self.assertEqual(download_file, result[0])

    def test_url_store_fetch_failure(self):
        """Test UrlBlobStore handles download failure"""
        def fail_download(url):
            raise Exception('Network error')

        store = blobstore.UrlBlobStore(
            'test-store', 50, 'test',
            'https://example.com/blob.bin', {})

        with unittest.mock.patch.object(tools, 'download',
                                        side_effect=fail_download):
            result = store.fetch('test,blob', '1.0', 'aarch64', 'generic')

        self.assertIsNone(result)

    def test_build_store_delegates_to_handler(self):
        """Test BuildBlobStore delegates to the blob handler"""
        # Set up config to use _testing handler
        blobstore._config = {
            'blobs': {
                'test,testing': {
                    'handler': '_testing',
                    'desc': 'Test blob'
                }
            }
        }

        store = blobstore.BuildBlobStore('build', 10, 'build from source')
        result = store.fetch('test,testing', '1.0', 'aarch64', 'generic')

        self.assertIsNotNone(result)
        fname, tmpdir = result
        self.assertTrue(os.path.exists(fname))

        # Clean up
        if tmpdir:
            shutil.rmtree(tmpdir)

    def test_fetch_blobs_success(self):
        """Test fetch_blobs with successful fetch"""
        blobstore._config = {
            'blobs': {
                'test,testing': {
                    'handler': '_testing',
                    'desc': 'Test blob'
                }
            }
        }

        with terminal.capture() as (stdout, _):
            result = Blob.fetch_blobs(['test,testing'], '1.0', 'aarch64',
                                      'generic')

        self.assertTrue(result)
        self.assertIn('Fetch:', stdout.getvalue())
        self.assertIn('cached to', stdout.getvalue())

        # Verify the blob was cached
        cache_path = os.path.join(self._indir, 'test,testing', '1.0',
                                  'aarch64', 'generic', 'test.bin')
        self.assertTrue(os.path.exists(cache_path))

    def test_fetch_blobs_failure(self):
        """Test fetch_blobs with failed fetch"""
        blobstore._config = {
            'blobs': {
                'test,fail': {
                    'handler': '_testing',
                    'desc': 'Test blob'
                }
            }
        }

        # Make the handler return None
        from binman.blobs._testing import Blob_testing
        original_build = Blob_testing.build

        def fail_build(self, version, arch, plat):
            return None

        with unittest.mock.patch.object(Blob_testing, 'build', fail_build):
            with terminal.capture() as (stdout, _):
                result = Blob.fetch_blobs(['test,fail'], '1.0', 'aarch64',
                                          'generic')

        self.assertFalse(result)
        self.assertIn('failed to fetch', stdout.getvalue())

    def test_fetch_with_local_store(self):
        """Test full fetch workflow using local store"""
        # Create a local blob file
        local_dir = os.path.join(self._indir, 'local_blobs')
        os.makedirs(local_dir)
        local_file = os.path.join(local_dir, 'firmware.bin')
        tools.write_file(local_file, b'local firmware')

        blobstore._config = {
            'stores': {
                'local': {
                    'type': 'local',
                    'priority': 20,
                    'desc': 'Local store'
                }
            },
            'blobs': {
                'test,local': {
                    'handler': '_testing',
                    'desc': 'Test local blob',
                    'stores': [
                        {'store': 'local', 'pattern': local_file}
                    ]
                }
            }
        }

        b = Blob('test,local', 'test')
        # Disable build by not having the handler support it
        with unittest.mock.patch.object(Blob, 'build', return_value=None):
            result = b.fetch('1.0', 'aarch64', 'generic', no_source=True)

        self.assertIsNotNone(result)
        self.assertEqual(local_file, result[0])

    def test_build_from_git_success(self):
        """Test build_from_git with mocked git and make"""
        output_content = b'built binary'

        def handle_command(pipe_list):
            cmd = pipe_list[0]
            if cmd[0] == 'git':
                tmpdir = cmd[-1]
                os.makedirs(tmpdir, exist_ok=True)
            elif cmd[0] == 'make':
                tmpdir = cmd[2]
                tools.write_file(os.path.join(tmpdir, 'output.bin'),
                                output_content)
            return command.CommandResult()

        try:
            command.TEST_RESULT = handle_command
            with terminal.capture() as (stdout, _):
                result = Blob.build_from_git(
                    'https://example.com/repo.git',
                    make_targets=['all'],
                    output_path='output.bin',
                    git_branch='main'
                )

            self.assertIsNotNone(result)
            fname, tmpdir = result
            self.assertTrue(os.path.exists(fname))
            self.assertEqual(output_content, tools.read_file(fname))
            self.assertIn('clone git repo', stdout.getvalue())

            # Clean up
            shutil.rmtree(tmpdir)
        finally:
            command.TEST_RESULT = None

    def test_build_from_git_no_output(self):
        """Test build_from_git when output file is not produced"""
        def handle_command(pipe_list):
            cmd = pipe_list[0]
            if cmd[0] == 'git':
                tmpdir = cmd[-1]
                os.makedirs(tmpdir, exist_ok=True)
            # Don't create output file for make
            return command.CommandResult()

        try:
            command.TEST_RESULT = handle_command
            with terminal.capture() as (stdout, _):
                result = Blob.build_from_git(
                    'https://example.com/repo.git',
                    make_targets=['all'],
                    output_path='missing.bin'
                )

            self.assertIsNone(result)
            self.assertIn('was not produced', stdout.getvalue())
        finally:
            command.TEST_RESULT = None

    def test_list_all_output(self):
        """Test list_all produces expected output"""
        blobstore._config = {
            'blobs': {
                'test,one': {'handler': 'h1', 'desc': 'First blob'},
                'test,two': {'handler': 'h2', 'desc': 'Second blob'}
            }
        }

        with terminal.capture() as (stdout, _):
            Blob.list_all()

        output = stdout.getvalue()
        self.assertIn('Compatible', output)
        self.assertIn('Description', output)
        self.assertIn('test,one', output)
        self.assertIn('First blob', output)
        self.assertIn('test,two', output)

    def test_list_stores_output(self):
        """Test list_stores produces expected output"""
        blobstore._config = {
            'stores': {
                'store1': {'type': 'local', 'priority': 20, 'desc': 'Local'},
                'store2': {'type': 'url', 'priority': 50, 'desc': 'Remote'}
            }
        }

        with terminal.capture() as (stdout, _):
            Blob.list_stores()

        output = stdout.getvalue()
        self.assertIn('Name', output)
        self.assertIn('Type', output)
        self.assertIn('Pri', output)
        self.assertIn('store1', output)
        self.assertIn('local', output)
        self.assertIn('store2', output)

    def test_show_info_output(self):
        """Test show_info produces expected output"""
        blobstore._config = {
            'stores': {
                'test-store': {'type': 'url', 'priority': 50}
            },
            'blobs': {
                'test,blob': {
                    'handler': 'test',
                    'desc': 'A test blob',
                    'stores': [
                        {'store': 'test-store', 'pattern': 'http://x/{version}'}
                    ]
                }
            }
        }

        with terminal.capture() as (stdout, _):
            Blob.show_info('test,blob')

        output = stdout.getvalue()
        self.assertIn('Compatible: test,blob', output)
        self.assertIn('Description: A test blob', output)
        self.assertIn('Handler: test', output)
        self.assertIn('test-store', output)

    def test_show_info_unknown_blob(self):
        """Test show_info for unknown blob"""
        blobstore._config = {'blobs': {}}

        with terminal.capture() as (stdout, _):
            Blob.show_info('unknown,blob')

        self.assertIn('Unknown blob', stdout.getvalue())

    def test_fetch_from_url_with_mock(self):
        """Test fetch_from_url with mocked download"""
        download_file = os.path.join(self._indir, 'url_download.bin')
        tools.write_file(download_file, b'url content')

        def fake_download(url):
            self.assertEqual('https://example.com/blob.bin', url)
            return download_file, None

        with unittest.mock.patch.object(tools, 'download',
                                        side_effect=fake_download):
            result = Blob.fetch_from_url('https://example.com/blob.bin')

        self.assertIsNotNone(result)
        self.assertEqual(download_file, result[0])

    def test_create_handler_from_config(self):
        """Test creating a handler based on YAML config"""
        blobstore._config = {
            'blobs': {
                'test,testing': {
                    'handler': '_testing',
                    'desc': 'Test blob'
                }
            }
        }

        handler = Blob.create('test,testing')
        self.assertIsNotNone(handler)
        self.assertEqual('test,testing', handler.compatible)

    def test_create_handler_unknown(self):
        """Test creating handler for unknown compatible raises error"""
        blobstore._config = {'blobs': {}}

        with self.assertRaises(ValueError) as exc:
            Blob.create('unknown,blob')

        self.assertIn('Cannot import blob module', str(exc.exception))

    def test_stores_sorted_by_priority(self):
        """Test that stores are returned sorted by priority"""
        blobstore._config = {
            'stores': {
                'low': {'type': 'url', 'priority': 100},
                'high': {'type': 'build', 'priority': 10},
                'medium': {'type': 'local', 'priority': 50}
            },
            'blobs': {
                'test,blob': {
                    'handler': '_testing',
                    'stores': [
                        {'store': 'low', 'pattern': 'x'},
                        {'store': 'high', 'pattern': ''},
                        {'store': 'medium', 'pattern': 'y'}
                    ]
                }
            }
        }

        stores = blobstore.get_stores_for_compatible('test,blob')
        priorities = [s.priority for s in stores]
        self.assertEqual([10, 50, 100], sorted(priorities))


class TestBlobYamlConfig(unittest.TestCase):
    """Tests for YAML configuration loading"""

    def setUp(self):
        """Set up test with a mock YAML config"""
        self._indir = tempfile.mkdtemp(prefix='blobtest.')
        Blob.set_blob_dir(self._indir)
        # Clear the config cache
        blobstore._config = None

    def tearDown(self):
        """Clean up"""
        if self._indir:
            shutil.rmtree(self._indir)
        blobstore._config = None

    def test_load_config_missing_file(self):
        """Test that missing config file returns empty dict"""
        # Point to a non-existent config file
        with unittest.mock.patch.object(blobstore, 'BINMAN_DIR', self._indir):
            config = blobstore._load_config()
            self.assertEqual({}, config)

    def test_get_handler_for_compatible(self):
        """Test getting handler name from compatible string"""
        test_config = {
            'blobs': {
                'arm,trusted-firmware-a': {
                    'handler': 'atf',
                    'desc': 'ARM Trusted Firmware'
                }
            }
        }
        blobstore._config = test_config
        handler = blobstore.get_handler_for_compatible('arm,trusted-firmware-a')
        self.assertEqual('atf', handler)

    def test_get_handler_for_compatible_not_found(self):
        """Test getting handler for unknown compatible returns None"""
        blobstore._config = {'blobs': {}}
        handler = blobstore.get_handler_for_compatible('unknown,blob')
        self.assertIsNone(handler)

    def test_get_blob_info(self):
        """Test getting blob information"""
        test_config = {
            'blobs': {
                'test,blob': {
                    'handler': 'test',
                    'desc': 'Test blob'
                }
            }
        }
        blobstore._config = test_config
        info = blobstore.get_blob_info('test,blob')
        self.assertEqual('test', info['handler'])
        self.assertEqual('Test blob', info['desc'])

    def test_get_all_blobs(self):
        """Test getting all blob definitions"""
        test_config = {
            'blobs': {
                'blob1': {'handler': 'h1'},
                'blob2': {'handler': 'h2'}
            }
        }
        blobstore._config = test_config
        blobs = blobstore.get_all_blobs()
        self.assertEqual(2, len(blobs))
        self.assertIn('blob1', blobs)
        self.assertIn('blob2', blobs)

    def test_get_stores_for_compatible(self):
        """Test getting stores configured for a compatible"""
        test_config = {
            'stores': {
                'test-store': {
                    'type': 'local',
                    'priority': 30,
                    'desc': 'Test store'
                }
            },
            'blobs': {
                'test,blob': {
                    'handler': 'test',
                    'stores': [
                        {'store': 'test-store', 'pattern': '/path/to/blob'}
                    ]
                }
            }
        }
        blobstore._config = test_config
        stores = blobstore.get_stores_for_compatible('test,blob')
        self.assertEqual(1, len(stores))
        self.assertEqual('test-store', stores[0].name)
        self.assertEqual(30, stores[0].priority)


if __name__ == '__main__':
    unittest.main()
