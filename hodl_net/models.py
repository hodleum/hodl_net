"""
Models, required for net full-functioning
"""

from sqlalchemy import Column, String
from typing import TypeVar, List, Any, Dict

from hodl_net.cryptogr import get_random, verify, sign, encrypt, decrypt
from hodl_net.errors import BadRequest, VerificationFailed, CryptogrError
from hodl_net.database import Base

import logging
import uuid
import attr
import time
import json

log = logging.getLogger(__name__)

T = TypeVar('T', int, str)
S = TypeVar('S', str, List[str])


class TempStructure:
    update_time = 5
    expire = 60

    def __init__(self):
        self.last_check = time.time()


class TempDict(dict, TempStructure):
    def __init__(self, *args, factory=list):
        dict.__init__(self, *args)
        TempStructure.__init__(self)
        self.factory = factory

    def __setitem__(self, key: T, value: Any):
        self.check()
        super().__setitem__(key, {
            'time': time.time(),
            'value': value
        })

    def __getitem__(self, key: T):
        self.check()
        if key not in self and self.factory:
            value = self.factory()
            self[key] = value
            return value
        return super().__getitem__(key)['value']

    def check(self):
        if time.time() - self.last_check < self.update_time:
            return
        for key, value in self.copy().items():
            if time.time() - value['time'] >= self.expire:
                del self[key]


@attr.s
class Message:
    """
    :param str name: Message name. It needs to call the handler functions
    :param data: Message data in dictionary
    :type data: dict or None
    """

    name = attr.ib(type=str)
    data = attr.ib(factory=dict)
    salt = attr.ib(type=str)
    callback = attr.ib(factory=lambda: str(uuid.uuid4()))

    @salt.default
    def _salt_gen(self):
        return get_random()

    @data.validator
    @name.validator
    def _check_type(self, attribute, value):
        if attribute.name == 'name' and not isinstance(value, str) or \
                attribute.name == 'data' and not isinstance(value, dict):
            raise BadRequest

    def dump(self):
        """
        Message to dict

        :rtype: dict
        """

        return attr.asdict(self)

    def to_json(self):
        """
        Message to JSON

        :return: JSON
        :rtype: str
        """

        return json.dumps(self.dump())

    @classmethod
    def from_json(cls, data: str):
        """
        Creates a class instance from JSON

        :param str data: Message in JSON
        :rtype: Message
        :raise hodl_net.errors.BadRequest: if fields in message have wrong type
        """

        return cls(**json.loads(data))


@attr.s
class MessageWrapper:
    """
    Wrapper for message

    :param message: Message to wrap. str, if encrypted
    :type message: Message or str

    :param str type: Type of message. Possible types:

        * 'shout' - if you want to notify all network. Not encrypted. Work like Broadcast
        * 'message' - if you want to send message directly.
          Encrypted, requires addressee's public_key key
        * 'request' - if you want to send message directly to peer via ip address.
          Not encrypted, not anonymous, not recommended to use.

    :param sender: Nickname of sender.
    :type sender: str or None

    :param str encoding: Encoding type of class Message. JSON default.

    :param str id: Message id. Generated automatically.
        If we receive two messages with the same id, one of them will be rejected.

    :param sign: Signature of message. None, if it is not encrypted.
    :type sign: str or None

    :param tunnel_id: ID of tunnel. None, if `MessageWrapper.type == 'request` or
        message already left a tunnel.
    :type tunnel_id: str or None


    .. UFO Alert!:: If message type is 'request', leave the field 'sender' empty.
        Otherwise you could be deanonymized.

    """
    message = attr.ib(type=Message, default=None)
    type = attr.ib(type=str, default='message')
    sender = attr.ib(type=str, default=None)
    encoding = attr.ib(default='json')
    id = attr.ib(type=str)
    sign = attr.ib(type=str, default=None)
    tunnel_id = attr.ib(type=str, default=None)

    acceptable_types = ['message', 'request', 'shout']
    acceptable_encodings = ['json']

    @id.default
    def _id_gen(self):
        return str(uuid.uuid4())

    @classmethod
    def from_bytes(cls, wrapper: bytes) -> 'MessageWrapper':
        """
        Load `MessageWrapper` from bytes.

        :rtype: MessageWrapper

        :raises hodl_net.errors.BadRequest: if fields in message have wrong type
        """
        try:
            wrapper = json.loads(wrapper.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise BadRequest
        message_type = wrapper.get('type')
        if not message_type or message_type not in cls.acceptable_types:
            raise BadRequest('Wrong message type')
        sender = wrapper.get('sender')
        if message_type != 'request' and (not sender or
                                          not isinstance(sender, str)):
            raise BadRequest('Sender name required')

        message = wrapper.get('message')
        if not message:
            raise BadRequest('Message required')
        if isinstance(message, dict):
            message = Message(**message)
        encoding = wrapper.get('encoding')
        if encoding not in cls.acceptable_encodings:
            raise BadRequest('Bad encoding')
        uid = wrapper.get('id')
        if not uid or not isinstance(uid, str):
            raise BadRequest('Id required')
        signature = wrapper.get('sign')
        if message_type != 'request' and (not signature or
                                          not isinstance(signature, str)):
            raise BadRequest('Sign required')
        tunnel_id = wrapper.get('tunnel_id')
        if tunnel_id and not isinstance(tunnel_id, str):
            raise BadRequest('Wrong metadata')

        wrapper = cls(
            message,
            message_type,
            sender,
            encoding,
            uid,
            signature,
            tunnel_id
        )
        return wrapper

    def encrypt(self, public_key: str):
        """
        Encrypt message (`self.message` type must be `Message`)

        :param str public_key: RSA public_key key of addressee
        :return: Encrypted message
        :rtype: str
        """
        if isinstance(self.message, str):
            return self.message
        return encrypt(self.message.to_json(), public_key)

    def decrypt(self, private_key: str):
        """
        Decrypt `Message` from string (`self.message type must be `str`)

        :param str private_key: RSA private key
        """
        if isinstance(self.message, dict):
            return
        self.message = json.loads(decrypt(self.message, private_key))

    def create_sign(self, private_key: str):
        self.sign = sign(self.message.to_json(), private_key)

    def verify(self, public_key: str):
        """
        Verify message in wrapper

        :param str public_key: RSA public_key key of sender
        :raises hodl_net.errors.VerificationFailed: if message has bad sign
        """
        if self.type == 'request':
            return
        if not verify(self.message.to_json(), self.sign, public_key):
            raise VerificationFailed('Bad signature')



    def prepare(self, private_key: str = None, public_key: str = None):
        """
        Prepare wrapper for send

        :param public_key: RSA public_key key of addressee.
            None if `MessageWrapper.type == 'request'`
        :type public_key: str or None

        :param private_key: our RSA private key.
            None if `MessageWrapper.type` == `'request'` or `'shout'`
        :type private_key: str or None

        """
        assert self.type != 'request' or not self.sender
        if self.type == 'request':
            return
        if not private_key and self.type != 'shout':
            raise CryptogrError('Private key is None')
        self.sign = sign(self.message.to_json(), private_key)
        self.message: Message = self.encrypt(public_key)

    def to_json(self):
        """
        MessageWrapper to JSON

        :return: JSON
        :rtype: str
        """
        return json.dumps(attr.asdict(self))


class Peer(Base):
    __tablename__ = 'peers'

    addr = Column(String, primary_key=True)

    def __init__(self, proto, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proto = proto

    def copy(self):
        return self

    def set_proto(self, proto):
        self.proto = proto

    def send(self, wrapper: MessageWrapper):
        """
        Send prepared Message with wrapper to peer.

        :param MessageWrapper wrapper: Wrapper to send

        .. warning:: Don't try to send `Message` without wrapper.
            Use `Peer.request` instead
        """
        if isinstance(wrapper, Message):
            log.warning('`Peer.send` method for sending requests is deprecated! '
                        'Use `Peer.request` instead')
            return self.request(wrapper)
        return self.proto._send(wrapper, self.addr)

    def request(self, message: Message):
        """
        Send request to Peer.

        .. warning:: Requests are unsafe.
            Don't try to send private information via `Peer.request`
        """
        log.debug(f'{self}: Send request {message}')
        wrapper = MessageWrapper(message, 'request')
        return self.proto._send(wrapper, self.addr)

    def response(self, to: Message, message: Message):
        message.callback = to.callback
        return self.request(message)

    def dump(self) -> Dict[str, str]:
        return {
            'address': self.addr
        }

    def __repr__(self):
        return f'<Peer {self.addr}>'


class User(Base):
    __tablename__ = 'users'

    public_key = Column(String)
    name = Column(String, primary_key=True)

    def __init__(self, proto, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proto = proto

    def send(self, message: Message):
        log.debug(f'{self}: Send {message}')
        return self.proto.send(message, self.name)

    def set_proto(self, proto):
        self.proto = proto

    def response(self, to: Message, message: Message):
        message.callback = to.callback
        return self.send(message)

    def dump(self) -> Dict[str, str]:
        return {
            'key': self.public_key,
            'name': self.name
        }


class Tunnels(TempDict):
    """
    Tunnel class
    """

    expire = 6000

    def add(self, tunnel_id: str, backward_peer: Peer, forward_peer: Peer):
        # TODO: docstring
        self[tunnel_id] = [backward_peer, forward_peer]

    def send(self, message: MessageWrapper):
        # TODO: docstring
        peers = self.get(message.tunnel_id)
        if not peers:
            return
        peers[1]._send(message)
