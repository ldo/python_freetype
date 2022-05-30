#+
# Setuptools script to install python_freetype. Make sure setuptools
# <https://setuptools.pypa.io/en/latest/index.html> is installed.
# Invoke from the command line in this directory as follows:
#
#     python3 setup.py build
#     sudo python3 setup.py install
#
# Written by Lawrence D'Oliveiro <ldo@geek-central.gen.nz>.
#-

import setuptools

setuptools.setup \
  (
    name = "Python FreeType",
    version = "0.62",
    description = "language bindings for FreeType",
    long_description = "language bindings for the FreeType library, for Python 3.2 or later",
    author = "Lawrence D'Oliveiro",
    author_email = "ldo@geek-central.gen.nz",
    url = "https://github.com/ldo/python_freetype",
    license = "FTL/LGPL v2.1+",
    py_modules = ["freetype2"],
  )
