from __future__ import absolute_import

import logging

def log_level(level_string):
	"""
	Return a log level for a string
	"""
	return getattr(logging, level_string.upper())

def add_arguments(parser):
	"""
	Add arguments to an ArgumentParser or OptionParser for purposes of
	grabbing a logging level.
	"""
	adder = (
		getattr(parser, 'add_argument', None)
		or getattr(parser, 'add_option')
	)
	adder('-l', '--log-level', default=logging.INFO, type=log_level,
		help="Set log level (DEBUG, INFO, WARNING, ERROR)")

def setup(options, **kwargs):
	"""
	Setup logging with options or arguments from an OptionParser or
	ArgumentParser. Also pass any keyword arguments to the basicConfig
	call.
	"""
	params = dict(kwargs)
	params.update(level=options.log_level)
	logging.basicConfig(**params)
