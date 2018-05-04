#+
# Distutils script to install python_freetype. Invoke from the command line
# in this directory as follows:
#
#     python3 setup.py install
#
# Written by Lawrence D'Oliveiro <ldo@geek-central.gen.nz>.
#-

import distutils.core

distutils.core.setup \
  (
    name = "Python FreeType",
    version = "0.6",
    description = "language bindings for FreeType",
    long_description = "language bindings for the FreeType library, for Python 3.2 or later",
    author = "Lawrence D'Oliveiro",
    author_email = "ldo@geek-central.gen.nz",
    url = "http://github.com/ldo/python_freetype",
    license = "FTL/LGPL v2.1+",
    py_modules = ["freetype2"],
  )
