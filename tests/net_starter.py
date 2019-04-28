import sys
from .protocol_for_tests import server
from hodl_net.database import create_db

port = int(sys.argv[1])
name = str(port)

server.prepare(port=port, name=name)
create_db(with_drop=True)
server.run()
