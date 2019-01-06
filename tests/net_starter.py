from hodl_net.protocol import server
from hodl_net.database import create_db
import sys

port = int(sys.argv[1])
name = str(port)

server.prepare(port=port, name=name)
create_db(with_drop=True)
server.run()
