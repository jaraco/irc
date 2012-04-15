import irclib

def test_version():
	assert 'VERSION' in vars(irclib)
	assert isinstance(irclib.VERSION, tuple)
	assert irclib.VERSION, "No VERSION detected."
