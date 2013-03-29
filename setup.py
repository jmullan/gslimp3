#!/usr/bin/env python
#
# Copyright (C) 2003 Gerome Fournier
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

DESCRIPTION = "Library implementing the SLIMP3 Client protocol"

import sys

from distutils.core import setup
if sys.version < '2.2.3':
    from distutils.dist import DistributionMetadata
    DistributionMetadata.classifiers = None
    DistributionMetadata.download_url = None

setup(
    name = "slimp3",
    version = "0.8.0",
    author = "Gerome Fournier", 
    author_email = "jef(at)foutaise.org",
    url = "http://foutaise.org/code/",
    license = "GPL",
    py_modules = ["slimp3"],
    description = DESCRIPTION,
    platforms = "any",
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: POSIX',
        'Operating System :: MacOS',
        'Topic :: Software Development :: Libraries :: Python Modules',
		'Topic :: Multimedia',
    ]
)
