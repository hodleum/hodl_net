Message format
==============

Message
-------

`hodl_net.models.Message` - тело сообщения. Любые функции для отправки сообщений ожидают экземпляр именно
этого класса. В нём есть два основных поля и два системных.


.. autoclass:: hodl_net.models.Message
    :members:

MessageWrapper
--------------

`hodl_net.models.MessageWrapper` - системная оболчка для сообщений, содержащая всю необходимую информацию.
Использовать и редактировать какие-либо поля этого класса не рекомендуется.

.. autoclass:: hodl_net.models.MessageWrapper
    :members:
