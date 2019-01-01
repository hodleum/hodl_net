# HODL-NET
// TODO: English docs

**HODL-NET** - распределённая зашифрованная анонимная самоорганизовывающаяся сеть поверх сети Интернет. Основной упор в реализации направлен на анонимность. Это достигается путём индификации пользователей исключительно по слепку публичного ключа, системы туннелирования и постоянной генерации "мусорных" сообщений.

### Пример простого протокола:

```python

from hodl_net.protocol import server, protocol
from hodl_net.models import Message

@server.on_open()
async def hello_world(_):
    response = await protocol.shout(Message(name='give_me_data'))
    print(repsonse.data['secret_data'])

@server.handle('give_me_data', 'shout')
async def send_secret_data(message):
    protocol.response(message, 
        Message(name='data', data={'secret_data': 'very_secret'})
    )
```
