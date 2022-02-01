from rosbridge_library.rosbridge_protocol import RosbridgeProtocol
from rosbridge_library.util.cbor import loads as decode_cbor

class RosbridgeProtocolCBOR(RosbridgeProtocol):

    def __init__(self, client_id, parameters):
        self.parameters = parameters
        RosbridgeProtocol.__init__(self, client_id)

        self.log(
            "warning", "Starting RosbridgeProtocolCBOR (extended to receive CBOR)")


    # We ovveride incoming losing fragmentation but adding cbor support
    def incoming(self, message_string=""):
        if self.bson_only_mode:
            self.buffer.extend(message_string)
        elif isinstance(message_string, bytes):
            msg = decode_cbor(message_string)
        else:
            self.buffer = self.buffer + str(message_string)
            msg = None

            # take care of having multiple JSON-objects in receiving buffer
            # ..first, try to load the whole buffer as a JSON-object
            try:
                msg = self.deserialize(self.buffer)
                if self.bson_only_mode:
                    self.buffer = bytearray()
                else:
                    self.buffer = ''

            # if loading whole object fails try to load part of it (from first opening bracket "{" to next closing bracket "}"
            # .. this causes Exceptions on "inner" closing brackets --> so I suppressed logging of deserialization errors
            except Exception as e:
                if self.bson_only_mode:
                    # Since BSON should be used in conjunction with a network handler
                    # that receives exactly one full BSON message.
                    # This will then be passed to self.deserialize and shouldn't cause any
                    # exceptions because of fragmented messages (broken or invalid messages might still be sent tough)
                    self.log("error", "Exception in deserialization of BSON")

                else:
                    # TODO: handling of partial/multiple/broken json data in incoming buffer
                    # this way is problematic when json contains nested json-objects ( e.g. { ... { "config": [0,1,2,3] } ...  } )
                    # .. if outer json is not fully received, stepping through opening brackets will find { "config" : ... } as a valid json object
                    # .. and pass this "inner" object to rosbridge and throw away the leading part of the "outer" object..
                    # solution for now:
                    # .. check for "op"-field. i can still imagine cases where a nested message ( e.g. complete service_response fits into the data field of a fragment..)
                    # .. would cause trouble, but if a response fits as a whole into a fragment, simply do not pack it into a fragment.
                    #
                    # --> from that follows current limitiation:
                    #     fragment data must NOT (!) contain a complete json-object that has an "op-field"
                    #
                    # an alternative solution would be to only check from first opening bracket and have a time out on data in input buffer.. (to handle broken data)
                    opening_brackets = [i for i, letter in enumerate(
                        self.buffer) if letter == '{']
                    closing_brackets = [i for i, letter in enumerate(
                        self.buffer) if letter == '}']

                    for start in opening_brackets:
                        for end in closing_brackets:
                            try:
                                msg = self.deserialize(
                                    self.buffer[start:end+1])
                                if msg.get("op", None) != None:
                                    # TODO: check if throwing away leading data like this is okay.. loops look okay..
                                    self.buffer = self.buffer[end +
                                                              1:len(self.buffer)]
                                    # jump out of inner loop if json-decode succeeded
                                    break
                            except Exception as e:
                                # debug json-decode errors with this line
                                # print e
                                pass
                        # if load was successfull --> break outer loop, too.. -> no need to check if json begins at a "later" opening bracket..
                        if msg != None:
                            break

        # if decoding of buffer failed .. simply return
        if msg is None:
            return

        # process fields JSON-message object that "control" rosbridge
        mid = None
        if "id" in msg:
            mid = msg["id"]
        if "op" not in msg:
            if "receiver" in msg:
                self.log("error", "Received a rosbridge v1.0 message.  Please refer to rosbridge.org for the correct format of rosbridge v2.0 messages.  Original message was: %s" % message_string)
            else:
                self.log("error", "Received a message without an op.  All messages require 'op' field with value one of: %s.  Original message was: %s" % (
                    list(self.operations.keys()), message_string), mid)
            return
        op = msg["op"]
        if op not in self.operations:
            self.log("error", "Unknown operation: %s.  Allowed operations: %s" %
                     (op, list(self.operations.keys())), mid)
            return
        # this way a client can change/overwrite it's active values anytime by just including parameter field in any message sent to rosbridge
        #  maybe need to be improved to bind parameter values to specific operation..
        if "fragment_size" in msg.keys():
            self.fragment_size = msg["fragment_size"]
            # print "fragment size set to:", self.fragment_size
        if "message_intervall" in msg.keys() and is_number(msg["message_intervall"]):
            self.delay_between_messages = msg["message_intervall"]
        if "png" in msg.keys():
            self.png = msg["msg"]

        # now try to pass message to according operation
        try:
            self.operations[op](msg)
        except Exception as exc:
            self.log("error", "%s: %s" % (op, str(exc)), mid)

        # if anything left in buffer .. re-call self.incoming
        # TODO: check what happens if we have "garbage" on tcp-stack --> infinite loop might be triggered! .. might get out of it when next valid JSON arrives since only data after last 'valid' closing bracket is kept
        if len(self.buffer) > 0:
            # try to avoid infinite loop..
            if self.old_buffer != self.buffer:
                self.old_buffer = self.buffer
                self.incoming()
