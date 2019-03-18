from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, defer
from collections import defaultdict
from typing import Callable, List
from hodl_net.models import (
    TempDict, Peer, User, Message, MessageWrapper, S
)
from hodl_net.errors import UnhandledRequest
from hodl_net.database import db_worker
from hodl_net.cryptogr import gen_keys
from hodl_net.globals import *
from hodl_net.discovery import LPD
from hodl_net.utils import NatWorker
from hodl_net.config_loader import load_conf

import sqlalchemy.exc

import logging
import random
import json
import uuid

log = logging.getLogger(__name__)

peer: Peer
user: User

conf_file = load_conf()  # TODO: Remove hard-coded configuration loading


def to_thread(f):
    def wrapper(*args, **kwargs):
        return reactor.callInThread(f, *args, **kwargs)

    return wrapper


def call_from_thread(f, *args, **kwargs):
    return reactor.callFromThread(f, *args, **kwargs)


class PeerProtocol(DatagramProtocol):
    """
    Main protocol for all interaction with net stack.
    """

    name = None  # TODO: names

    def __init__(self, _server: 'Server', r: reactor):
        self.reactor = r
        self.server = _server

        self.temp = TempDict(factory=None)
        self.tunnels = TempDict(factory=None)
        self.public_key, self.private_key = None, None

    def prepare_keys(self):
        try:
            with open(f'{self.name}_keys') as f:
                self.public_key, self.private_key = json.loads(f.read())
        except FileNotFoundError:
            self._gen_keys()

    def _gen_keys(self):
        self.private_key, self.public_key = gen_keys()
        with open(f'{self.name}_keys', 'w') as f:
            log.info(f'keys generated {self.name}')
            f.write(json.dumps([self.public_key, self.private_key]))

    def copy(self) -> 'PeerProtocol':
        return self

    # noinspection PyUnresolvedReferences,PyDunderSlots
    def datagramReceived(self, datagram: bytes, addr: tuple):
        try:
            return self.handle_datagram(datagram, addr)
        except Exception as _:
            log.exception('Exception during handling message.')

    def handle_datagram(self, datagram: bytes, addr: tuple):
        ses = db_worker.get_session()
        addr = ':'.join(map(str, addr))
        log.debug(f'Datagram received {datagram}')
        wrapper = MessageWrapper.from_bytes(datagram)

        if wrapper.type != 'request':
            if wrapper.tunnel_id:
                if random.randint(0, 3) != random.randint(0, 3):  # TODO: safe random func
                    return self.forward(wrapper)
                wrapper.type = 'message'
                wrapper.tunnel_id = None

            if wrapper.id in self.temp:
                return
            else:
                self.temp[wrapper.id] = wrapper
                self._send_all(wrapper)

        # Decryption message, preparing to process

        _peer = ses.query(Peer).filter_by(addr=addr).first()
        if not _peer:
            _peer = Peer(self, addr=addr)
            ses.add(_peer)
            ses.commit()
            log.debug(f'New peer {addr}')
            _peer.request(Message('share'))
        _peer.proto = self

        _user = None
        if wrapper.sender:
            _user = ses.query(User).filter_by(name=wrapper.sender).first()
            if not local.user:
                return db_worker.close_session(ses)

            try:
                wrapper.decrypt(self.private)
            except ValueError:
                return db_worker.close_session(ses)

        callbacks = self.server._callbacks[wrapper.message.callback]
        if callbacks:
            for i in range(len(callbacks)):
                call = callbacks.pop()
                if call:
                    call.callback(wrapper.message)
            return db_worker.close_session(ses)
        session.commit()
        session.close()
        for func in self.server._handlers[wrapper.type][wrapper.message.name]:
            if func:
                func(wrapper.message, _peer, _user)
        if not self.server._handlers[wrapper.type][wrapper.message.name]:
            raise UnhandledRequest

    def forward(self, wrapper: MessageWrapper):
        return self.random_send(wrapper)  # TODO: Check exists tunnels

    def _send(self, wrapper: MessageWrapper, addr):
        """
        Low level send.

        :param MessageWrapper wrapper: wrapper to send
        :param addr: address
        :type addr: tuple or str

        """
        if not wrapper:
            return
        if isinstance(addr, str):
            addr: list = addr.split(':')
            addr[1] = int(addr[1])
            addr = tuple(addr)
        self.transport.write(wrapper.to_json().encode('utf-8'), addr)
        d = defer.Deferred()
        self.server._callbacks[wrapper.message.callback].append(d)
        return d

    def send(self, message: Message, name: str):
        """
        High level send
        """
        addressee: User = self.session.query(User).filter_by(name=name).first()
        wrapper = MessageWrapper(
            message,
            type='message',
            sender=self.name,
            tunnel_id=str(uuid.uuid4()),  # TODO: check exists tunnels
        )
        wrapper.prepare(self.private_key, addressee.public_key)
        return self.random_send(wrapper)

    def shout(self, message: Message):
        """
        High level send_all
        """
        wrapper = MessageWrapper(
            message,
            type='shout',
            sender=self.name,
            tunnel_id=str(uuid.uuid4())
        )
        return self.random_send(wrapper)  # TODO: await generator

    @property
    @db_worker.with_session
    def peers(self) -> List[Peer]:
        """
        All peers in DB
        """
        peers = []
        for _peer in session.query(Peer).all():
            _peer.proto = self
            peers.append(_peer)
        return peers  # TODO: generator mb

    def add_peer(self, _peer: Peer, method=None):
        ses = db_worker.get_session()
        ses.add(_peer)

        try:
            ses.commit()
            if method:
                log.info("Peer {} discovered by {}".format(_peer.addr, method))
            else:
                log.info("Peer {} discovered".format(_peer.addr))
        except sqlalchemy.exc.IntegrityError:
            pass
        db_worker.close_session(ses)

    def send_all(self, message: Message):
        """
        Send request to all peers

        :param message: Message to send
        :return:
        """
        for _peer in self.peers:
            _peer.request(message)

    def _send_all(self, wrapper: MessageWrapper):
        for _peer in self.peers:
            _peer.send(wrapper)

    def random_send(self, wrapper: MessageWrapper):
        """
        Send MessageWrapper to random peer
        :param wrapper: MessageWrapper Instance
        :return:
        """
        return random.choice(self.peers).send(wrapper)


class Server:
    """
    Main Server Class
    """
    _handlers = defaultdict(lambda: defaultdict(lambda: []))
    _callbacks = TempDict()
    _on_close_func = None
    _on_open_func = None
    ext_addr = (None, None)

    def __init__(self,
                 port: int = conf_file['main']['port'],
                 white: bool = True,
                 lpd_port: int = conf_file['lpd']['port'],
                 lpd_ip: str = conf_file['lpd']['multicast_ip'],
                 lpd_interval: int = conf_file['lpd']['send_interval']):
        """

        :param port: port to start server
        :param white: is ip white
        """
        from twisted.internet import reactor

        self.port = port
        self.lpd_port = lpd_port
        self.lpd_ip = lpd_ip
        self.lpd_interval = lpd_interval
        self.white = white

        self.reactor = reactor
        self.udp = PeerProtocol(self, reactor)

        if conf_file['lpd']['enabled']:

            self.lpd = LPD(self,
                           self.lpd_port,
                           self.port,
                           self.lpd_ip,
                           self.lpd_interval)

        self.prepared = False

    def handle(self, event: S, _type: str = 'message', in_thread: bool = True) -> Callable:
        """

        @server.handle('echo')
        async def echo(message):
            answer = await user.send(Message('echo_response', message.data)
            print(answer.data)

        @server.handle('echo', 'request')
        async def echo_request(message):
            peer.request(Message('echo_response', message.data)


        """

        if isinstance(event, str):
            event = [event]

        def decorator(func: Callable):

            # noinspection PyUnresolvedReferences,PyDunderSlots
            def wrapper(message: Message, _peer: Peer = None, _user: User = None):
                local.peer = _peer
                local.user = _user
                d = func(message)
                return defer.ensureDeferred(d)

            if in_thread:
                wrapper = to_thread(wrapper)
            for e in event:
                self._handlers[_type][e].append(wrapper)
            return func

        return decorator

    def prepare(self, port: int = None, name: str = None):
        """
        Server preparing function.

        :param port: Port on which we should start server
        :param name: Server name
        :return:
        """

        self.port = port if port else self.port
        self.udp.name = name if name else self.udp.name

        self.udp.name = name
        self.udp.prepare_keys()

        db_worker.create_connection(f'{self.udp.name}_db.sqlite')

        logging.basicConfig(level=logging.DEBUG,
                            format=f'%(name)s.%(funcName)-20s [LINE:%(lineno)-3s]# [{self.port}]'
                            f' %(levelname)-8s [%(asctime)s]  %(message)s')
# print(conf_file)
        self.reactor.listenUDP(self.port, self.udp)

        if conf_file['lpd']['enabled']:
            self.reactor.listenMulticast(self.lpd_port, self.lpd, listenMultiple=True)

        log.info(f'Core started at {self.port}')

        if conf_file['upnp']['enabled']:
            nat_worker = NatWorker()

            if nat_worker:
                self.ext_addr = nat_worker.get_addrs()

        log.info("Plugin loading finished.")

        self.prepared = True

    def run(self, *args, **kwargs):
        if not self.prepared:
            self.prepare(*args, **kwargs)
        self.reactor.run()

    @property
    def name(self):
        return self.udp.name

    def set_name(self, name):
        self.udp.name = name


server = Server()
protocol = server.udp
