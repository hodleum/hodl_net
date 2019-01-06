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

import logging
import random
import json
import uuid

log = logging.getLogger(__name__)

peer: Peer
user: User


def to_thread(f):
    def wrapper(*args, **kwargs):
        return reactor.callInThread(f, *args, **kwargs)

    return wrapper


class PeerProtocol(DatagramProtocol):
    """
    Main protocol for all interaction with net.
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

    @db_worker.with_session
    def handle_datagram(self, datagram: bytes, addr: tuple):
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

        _peer = session.query(Peer).filter_by(addr=addr).first()
        if not _peer:
            _peer = Peer(self, addr=addr)
            session.add(_peer)
            session.commit()
            log.debug(f'New peer {addr}')
            _peer.request(Message('share'))
        _peer.proto = self

        _user = None
        if wrapper.sender:
            _user = session.query(User).filter_by(name=wrapper.sender).first()
            if not local.user:
                return

            try:
                wrapper.decrypt(self.private)
            except ValueError:
                return

        callbacks = self.server._callbacks[wrapper.message.callback]
        if callbacks:
            for i in range(len(callbacks)):
                call = callbacks.pop()
                if call:
                    call.callback(wrapper.message)
            return

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

    def send_all(self, message: Message):
        """
        Send request to all peers
        """
        for _peer in self.peers:
            _peer.request(message)

    def _send_all(self, wrapper: MessageWrapper):
        for _peer in self.peers:
            _peer.send(wrapper)

    def random_send(self, wrapper: MessageWrapper):
        """
        Send MessageWrapper to random peer
        """
        return random.choice(self.peers).send(wrapper)


class Server:
    _handlers = defaultdict(lambda: defaultdict(lambda: []))
    _callbacks = TempDict()
    _on_close_func = None
    _on_open_func = None

    def __init__(self, port: int = 8000, white: bool = True):
        from twisted.internet import reactor

        self.port = port
        self.white = white

        self.reactor = reactor
        self.udp = PeerProtocol(self, reactor)

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
        # TODO: docstring

        self.port = port if port else self.port
        self.udp.name = name if name else self.udp.name

        self.udp.name = name
        self.udp.prepare_keys()

        db_worker.create_connection(f'{self.udp.name}_db.sqlite')

        logging.basicConfig(level=logging.DEBUG,
                            format=f'%(name)s.%(funcName)-20s [LINE:%(lineno)-3s]# [{self.port}]'
                            f' %(levelname)-8s [%(asctime)s]  %(message)s')

        self.reactor.listenUDP(self.port, self.udp)
        log.info(f'Started at {self.port}')
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
