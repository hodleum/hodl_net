from hodl_net import server, peer
from hodl_net.models import Message


@server.handle('echo', 'request')
async def echo(message):
    peer.response(message, Message('echo_resp', {
        'msg': message.data['msg']
    }))
