import unittest
from subprocess import Popen
from sys import stdout, stderr
import time
from threading import Thread
from twisted.internet.defer import ensureDeferred

from hodl_net import protocol
from hodl_net.database import create_db
from hodl_net.models import Peer, Message


def async_test(func):
    def wrapper(*args, **kwargs):
        return ensureDeferred(func(*args, **kwargs))

    return wrapper


class NetTest(unittest.TestCase):
    server_counts = 6
    servers = []

    @classmethod
    def setUpClass(cls):

        time.sleep(1)
        for i in range(8001, 8000 + cls.server_counts):
            cls.servers.append(Popen(['python', 'net_starter.py', str(i)], stdout=stdout, stderr=stderr))
            time.sleep(1)
        time.sleep(3)

    def test_share_peers(self):
        for i in range(8001, 8000 + self.server_counts):
            peer = Peer(protocol, addr=f'127.0.0.1:{i}')
            peer.request(Message('ping'))
        time.sleep(3)
        self.assertEqual(len(protocol.peers), self.server_counts)
        protocol.send_all(Message('ping'))
        time.sleep(1)

    @async_test
    async def test_peer_response(self):
        peer = Peer(protocol, addr=f'127.0.0.1:8001')
        resp = await peer.request(Message('echo', {'msg': 'test'}))
        self.assertDictEqual(resp.data, {'msg': 'test'})

    @classmethod
    def tearDownClass(cls):
        for server in cls.servers:
            server.kill()
        main_server.reactor.stop()


if __name__ == '__main__':
    import sys
    sys.path.append('../')
    from tests.protocol_for_tests import server as main_server

    print(sys.path)

    test_thread = Thread(target=unittest.main)
    main_server.reactor.callLater(0, test_thread.start)

    main_server.prepare(port=8000, name='8000')
    create_db(with_drop=True)
    main_server.run()
