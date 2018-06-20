import threading

import pytest

import irc.server


class TestClient(irc.server.IRCClient):
	def __init__(self, *args, **kwargs):
		super(TestClient, self).__init__(*args, **kwargs)
		self.messages = []

	def handle_pubmsg(self, params):
		self.messages.append(params)


@pytest.fixture
def irc_server(scope='session'):
	bind_address = '::1', 0
	server = irc.server.IRCServer(bind_address, TestClient)
	try:
		threading.Thread(target=server.serve_forever).start()
		yield server
	finally:
		server.shutdown()
		server.server_close()
