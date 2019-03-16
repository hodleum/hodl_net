class Core:

    class PeerProtocol():
        def __init__(self):
            self.peers = []

    def __init__(self):
        self.udp = self.PeerProtocol()
