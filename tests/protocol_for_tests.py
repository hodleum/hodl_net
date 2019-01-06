from hodl_net import server, peer
from hodl_net.models import Message
import time


@server.handle('echo', 'request')
async def echo(message):
    peer.response(message, Message('echo_resp', {
        'msg': message.data['msg']
    }))


@server.handle('test_non_block', 'request')
async def test_non_block(message):
    print('Thread stopped')
    time.sleep(10)
    print('Thread started')
    peer.response(message, message)
