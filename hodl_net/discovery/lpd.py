"""
Local Peer Discovery realization for Hodleum Networking Stack

Changelog:
v0.0.1 by DanGSun - Basic Realization

"""

from twisted.internet.protocol import DatagramProtocol
from json import dumps, loads
from time import sleep
from threading import Thread
from hodl_net.discovery.core_emul import Core
from hodl_net.models import Peer
from hodl_net.server import db_worker, PeerProtocol


class LPD(DatagramProtocol):

    def __init__(self, core, lpd_port=9999, main_port=8000):
        self.core = core
        self.lpd_port = lpd_port
        self.main_port = main_port

    def announce(self):

        data = {
            'prt': {
                'nm': "HDN-NetStack",
                'v': '2.0'
            },

            'gl': "LPD",
            'dt': {
                'prt': self.main_port
            }
        }

        while True:
            self.transport.write(dumps(data).encode(), ("228.0.0.5", self.lpd_port))
            sleep(2)

    def startProtocol(self):

        # Join the multicast address, so we can receive replies:
        self.transport.joinGroup("228.0.0.5")
        # Send to 228.0.0.5:9999 - all listeners on the multicast address
        # (including us) will receive this message.

        Thread(target=self.announce).start()

    def datagramReceived(self, datagram, address):
        print("Datagram %s received from %s" % (repr(datagram), repr(address)))
        dtgrm = loads(datagram.decode())
        addr = "{}:{}".format(address[0], dtgrm['dt']['prt'])
        ses = db_worker.get_session()
        _peer = Peer(self, addr=addr)
        if _peer not in self.core.udp.peers:
            ses.add(_peer)
            ses.commit()
        ses.close()
        print(self.core.udp.peers)


if __name__ == '__main__':
    'Testing'
    from twisted.internet import reactor

    reactor.listenMulticast(9999, LPD(Core()), listenMultiple=True)
    reactor.run()
