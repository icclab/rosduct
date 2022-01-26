import sys
import threading
from twisted.python import log
from twisted.internet import reactor, ssl
from autobahn.twisted.websocket import WebSocketClientProtocol, WebSocketClientFactory, connectWS

bridge = None

class ROSBridgeClient():

    def __init__(self, ws_url, bridge_ref):
        global bridge
        self.factory = ROSBridgeWSClientFactory(ws_url)
        bridge = bridge_ref
        connectWS(self.factory)
        reactor.run()


class ROSBridgeWSClient(WebSocketClientProtocol):

    def onConnect(self, response):
        print("OnConnect:" + str(response))

    def onOpen(self):
        # print("OnOpen")
        # print("Bridge: " + str(bridge))
        # # self.sendMessage(u"Hello, world!".encode('utf8'))
        bridge.init_bridge(self)

    def onMessage(self, payload, isBinary):
        if isBinary:
            print("Binary message received: {0} bytes".format(len(payload)))
            # bridge.incoming_queue.push(payload)
        else:
            message = payload.decode('utf8')
            # print("Text message received: {0}".format(message))
            # bridge.incoming_queue.push(message)
            bridge.protocol.incoming(message_string=message)


class ROSBridgeWSClientFactory(WebSocketClientFactory):
    protocol = ROSBridgeWSClient

    def clientConnectionFailed(self, connector, reason):
        print("Connection failed - goodbye!")
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        print("Connection lost - reason: {0}".format(reason))
        # reconnect
        connectWS(self)
        # reactor.stop()


class EchoWSClient(WebSocketClientProtocol):

    def onConnect(self, response):
        print("OnConnect:" + str(response))

    def onOpen(self):
        print("OnOpen")
        self.sendMessage(u"Hello, world!".encode('utf8'))

    def onMessage(self, payload, isBinary):
        if isBinary:
            print("Binary message received: {0} bytes".format(len(payload)))
        else:
            print("Text message received: {0}".format(payload.decode('utf8')))


if __name__ == '__main__':
    log.startLogging(sys.stdout)
    factory = ROSBridgeWSClientFactory("wss://rosbridge.k8sbeta.init-lab.ch")
    factory.protocol = EchoWSClient
    connectWS(factory)
    reactor.run()
