import signal
import sys
from time import sleep

from autobahn.twisted.websocket import (WebSocketClientFactory,
                                        WebSocketClientProtocol, connectWS)
from autobahn.websocket.compress import (PerMessageDeflateOffer,
                                         PerMessageDeflateResponse,
                                         PerMessageDeflateResponseAccept)
from twisted.internet import reactor
from twisted.python import log
from twisted.internet import reactor, ssl
from autobahn.twisted.websocket import WebSocketClientProtocol, WebSocketClientFactory, connectWS
from autobahn.websocket.compress import PerMessageDeflateOffer, \
    PerMessageDeflateOfferAccept, \
    PerMessageDeflateResponse, \
    PerMessageDeflateResponseAccept
import rospy

bridge = None


class ROSBridgeClient():

    def __init__(self, ws_url, bridge_ref):
        global bridge
        self.factory = ROSBridgeWSClientFactory(ws_url)
        self.factory.protocol = ROSBridgeWSClient
        # self.factory.protocol.log.set_log_level("debug")
        bridge = bridge_ref
        connectWS(self.factory)
        reactor.run()

    def stop(self):
        self.factory.stopped = True
        self.factory.loseConnection()
        self.factory.clientConnectionFailed()
        reactor.stop()


class ROSBridgeWSClient(WebSocketClientProtocol):

    def onConnect(self, response):
        print("Connected. WebSocket extensions in use: {}".format(
            response.extensions))

    def onOpen(self):
        print("OnOpen")
        bridge.init_bridge(self)

    def onMessage(self, payload, isBinary):
        # print("Message received")
        # print("Message payload type: {0}".format(type(payload)))
        if isBinary:
            # print("Binary message received: {0} bytes".format(len(payload)))
            # message = decode_cbor(payload)
            # we leave the payload in bytes and decode it later
            message = payload
            # print("Binary message decoded: {0}".format(message))
        else:
            # print("Text message received: {0}".format(len(payload)))
            message = payload.decode('utf8')
            # print("Text message received: {0}".format(message))
        bridge.incoming_queue.push(message)
        # bridge.protocol.incoming(message)


class ROSBridgeWSClientFactory(WebSocketClientFactory):
    sleep_time = 1

    def __init__(self, url):
        WebSocketClientFactory.__init__(self, url)
        # Enable WebSocket extension "permessage-deflate".

        # The extensions offered to the server ..
        offers = [PerMessageDeflateOffer()]
        self.setProtocolOptions(perMessageCompressionOffers=offers)

        # Function to accept responses from the server ..
        def accept(response):
            if isinstance(response, PerMessageDeflateResponse):
                print("Received PerMessageDeflateResponse")
                return PerMessageDeflateResponseAccept(response)

        self.setProtocolOptions(perMessageCompressionAccept=accept)

    def clientConnectionFailed(self, connector, reason):
        print("Connection failed - goodbye!")
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        print("Connection lost - reason: {0}".format(reason))
        if not rospy.is_shutdown():
            # sleep exponential time
            print("Sleeping {0} secs".format(self.sleep_time))
            sleep(self.sleep_time)
            self.sleep_time *= 2
            # reconnect
            print("Reconnecting...")
            connectWS(self)
        else:
            reactor.stop()


class EchoWSClient(WebSocketClientProtocol):

    def onConnect(self, response):
        print("WebSocket extensions in use: {}".format(response.extensions))

    def onOpen(self):
        print("OnOpen")
        self.sendMessage(u"Hello, world!".encode('utf8'))

    def onMessage(self, payload, isBinary):
        if isBinary:
            print("Binary message received: {0} bytes".format(len(payload)))
        else:
            print("Text message received: {0}".format(payload.decode('utf8')))


def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    reactor.stop()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    if len(sys.argv) < 2:
        print("Need the WebSocket server address, i.e. ws://127.0.0.1:9000")
        sys.exit(1)

    log.startLogging(sys.stdout)
    factory = ROSBridgeWSClientFactory(sys.argv[1])
    factory.protocol = EchoWSClient
    factory.protocol.log.set_log_level("debug")
    connectWS(factory)
    reactor.run()
