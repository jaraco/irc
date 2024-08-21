import contextlib

try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata  # type: ignore[no-redef]


def _get_version():
    with contextlib.suppress(Exception):
        return metadata.version('irc')
    return 'unknown'
