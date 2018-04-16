import sys
import fnmatch
import os

collect_ignore = ["setup.py"]

if sys.version_info < (3, 5):
    for root, dirnames, filenames in os.walk('.'):
        for filename in fnmatch.filter(filenames, '*aio.py'):
            collect_ignore.append(os.path.join(root, filename))
