from hodl_net.protocol import server
import sys

port = int(sys.argv[1])
name = str(port)

server.prepare(port=port, name=name)
server.create_db(with_drop=True)
server.run()
