import sys


if sys.version_info >= (3, 12):
    from importlib.resources import files
else:
    from importlib_resources import files  # noqa: F401
