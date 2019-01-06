from hodl_net.models import *
from hodl_net.server import peer, protocol, server, session


@server.handle('share', 'request', in_thread=False)
async def share_peers(_):
    peers = [_peer.dump() for _peer in session.query(Peer).all()]
    users = [_user.dump() for _user in session.query(User).all()]
    peer.request(Message(
        name='share_info',
        data={
            'users': users,
            'peers': peers
        }
    ))


@server.handle('new_user', 'shout', in_thread=False)
async def record_new_user(message):
    data = message.data
    new_user = session.query(User).filter_by(name=name).first()
    if not new_user:
        new_user = User(protocol, public_key=data['key'], name=data['name'])
        session.add(new_user)
        session.commit()
        protocol.send_all(Message(
            name='new_user',
            data=new_user.dump()
        ))


@server.handle('share_info', 'request', in_thread=False)
async def record_peers(message):
    for data in message.data['peers']:
        if not session.query(Peer).filter_by(addr=data['address']).first():
            new_peer = Peer(protocol, addr=data['address'])
            session.add(new_peer)  # TODO: test new peers

    for data in message.data['users']:
        if not session.query(User).filter_by(name=data['name']):
            new_user = Peer(protocol, public_key=data['key'], name=data['name'])
            session.add(new_user)
    session.commit()


@server.handle('ping', 'request')
async def ping(_):
    pass


if __name__ == '__main__':
    server.run()
