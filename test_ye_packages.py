import importlib.machinery
import importlib.util
import os
import pathlib
import unittest
from unittest import mock


def load_ye():
    os.environ.setdefault('YE_EDITOR', 'true')
    path = pathlib.Path(__file__).with_name('ye')
    loader = importlib.machinery.SourceFileLoader('ye_module', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class PackageArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ye = load_ye()

    def test_pkg_tarball_selects_gzip_data_archive(self):
        members = ['debian-binary', 'control.tar.gz', 'data.tar.gz']
        with mock.patch.object(self.ye, 'ar_members', return_value=members):
            self.assertEqual(self.ye.pkg_tarball('package.ipk', 'data'),
                             'data.tar.gz')

    def test_pkg_tarball_selects_xz_data_archive(self):
        members = ['debian-binary', 'control.tar.gz', 'data.tar.xz']
        with mock.patch.object(self.ye, 'ar_members', return_value=members):
            self.assertEqual(self.ye.pkg_tarball('package.ipk', 'data'),
                             'data.tar.xz')

    def test_pkg_tarball_selects_zstd_data_archive(self):
        members = ['debian-binary', 'control.tar.gz', 'data.tar.zst']
        with mock.patch.object(self.ye, 'ar_members', return_value=members):
            self.assertEqual(self.ye.pkg_tarball('package.ipk', 'data'),
                             'data.tar.zst')

    def test_pkg_tarball_selects_compressed_control_archive(self):
        members = ['debian-binary', 'control.tar.zst', 'data.tar.zst']
        with mock.patch.object(self.ye, 'ar_members', return_value=members):
            self.assertEqual(self.ye.pkg_tarball('package.ipk', 'control'),
                             'control.tar.zst')


if __name__ == '__main__':
    unittest.main()
