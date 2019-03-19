"""
Local Peer Discovery realization for Hodleum Networking Stack

Changelog:
v0.0.1 by DanGSun - Basic Realization

"""

import logging
import json

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import task
from twisted.internet import reactor

from time import sleep

from hodl_net.discovery.core_emul import Core
from hodl_net.models import Peer

log = logging.getLogger(__name__)


class LPD(DatagramProtocol):

    def __init__(self,
                 core,
                 lpd_port: int = 9999,
                 main_port: int = 8000,
                 multicast_ip: str = '224.0.0.1',
                 lpd_interval: int = 2):

        self.core = core
        self.lpd_port = lpd_port
        self.lpd_ip = multicast_ip
        self.main_port = main_port
        self.announce_interval = lpd_interval
        self.data = {
            'prt': {
                'nm': "HDN-NetStack",
                'v': '2.0'
            },

            'gl': "LPD",
            'dt': {
                'prt': self.main_port
            }
        }

        self.announcer = task.LoopingCall(self.announce)

    def announce(self):

        try:
            self.transport.write(json.dumps(self.data).encode(), (self.lpd_ip, self.lpd_port))
        except AttributeError:
            log.debug("Detected an AttributeError... Handling it, like a program stop")
            self.announcer.stop()
            log.info("LPD Caster Stopped...")

    def startProtocol(self):
        log.info(f"LPD Started at {self.lpd_port}")
        self.announcer.start(self.announce_interval)
        # Join the multicast address, so we can receive replies:
        self.transport.joinGroup(self.lpd_ip)

    def datagramReceived(self, datagram, address):
        dtgrm = json.loads(datagram.decode())
        addr = "{}:{}".format(address[0], dtgrm['dt']['prt'])
        _peer = Peer(self, addr=addr)
        if _peer not in self.core.udp.peers:
            self.core.udp.add_peer(_peer, "LPD")


if __name__ == '__main__':
    'Testing'
    from twisted.internet import reactor

    reactor.listenMulticast(9999, LPD(Core()), listenMultiple=True)
    reactor.run()
