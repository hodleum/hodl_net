# HODL-NETv2.0 [![Documentation Status](https://readthedocs.org/projects/hodl-net/badge/?version=latest)](https://hodl-main.readthedocs.io/projects/net/ru/latest/?badge=latest)    [![Build Status](https://travis-ci.org/hodleum/hodl_net.svg?branch=master)](https://travis-ci.org/hodleum/hodl_net)


**HODL-NET** - decentralized encrypted anonymous self-creating network overlay over Internet. Main goal of this project - total anonimity. We achieve it by using user auth by hash of public key, tunneling system and continously generation of "trash" messages.

### Simple Usage Example:

```python

from hodl_net.protocol import server, protocol
from hodl_net.models import Message


@server.on_open()
async def hello_world(_):
    response = await protocol.shout(Message(name='give_me_data'))
    print(response.data['secret_data'])


@server.handle('give_me_data', 'shout')
async def send_secret_data(message):
    protocol.response(message, 
        Message(name='data', data={'secret_data': 'very_secret'})
    )
```

More info:
* [Documentation](https://hodl-main.readthedocs.io/projects/net/ru/latest/?badge=latest)
* [Project on PyPI]()
* Email us at net_team@hodleum.org


# Todo:

* DHT
* Local Peer Discovery
* API For Alternative Peer Discovery Methods
* Peer Map Builder
