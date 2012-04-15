import irc.client

def test_version():
	assert 'VERSION' in vars(irc.client)
	assert isinstance(irc.client.VERSION, tuple)
	assert irc.client.VERSION, "No VERSION detected."
