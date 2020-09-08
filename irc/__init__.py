import contextlib

try:
    from importlib import metadata  # type: ignore
except ImportError:
    import importlib_metadata as metadata  # type: ignore


def _get_version():
    with contextlib.suppress(Exception):
        return metadata.version('irc')
    return 'unknown'
