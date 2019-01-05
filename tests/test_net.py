import unittest
from subprocess import Popen
from sys import stdout, stderr
import time
from threading import Thread

from hodl_net.protocol import server as main_server, protocol
from hodl_net.models import Peer, Message


class NetTest(unittest.TestCase):
    server_counts = 10
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

    @classmethod
    def tearDownClass(cls):
        for server in cls.servers:
            server.kill()
        main_server.reactor.stop()


if __name__ == '__main__':
    test_thread = Thread(target=unittest.main)
    main_server.reactor.callLater(0, test_thread.start)

    main_server.prepare(port=8000, name='8000')
    main_server.create_db(with_drop=True)
    main_server.run()
