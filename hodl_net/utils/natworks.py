import upnpclient
import logging

log = logging.getLogger(__name__)


class NatWorker:

    def __init__(self, main_port=8000, timeout=2):
        log.info("UPnP Passthrough Service Started.")
        log.debug("Fetching a device list...")
        self.dev_list = upnpclient.discover(timeout)
        log.debug(f"Fetch finished in {timeout}s")
        log.debug(f"Devices detected: {self.dev_list}")
        if not self.dev_list:
            log.warning("No UPnP Devices was found. Stopping NatWorker...")
            del self

    def get_addrs(self):
        return (None, None)  # TODO: Return real ext IP and port


if __name__ == '__main__':
    logging.basicConfig(format=logging.BASIC_FORMAT)
    log.setLevel(logging.DEBUG)
    nw = NatWorker()
