#!/usr/bin/env python3 -m
import sys
import signal
from rosapi.srv import Topics, Publishers
import rospy
from rosduct.srv import ROSDuctConnection, ROSDuctConnectionResponse
from .conversions import from_dict_to_JSON
from .conversions import from_JSON_to_dict
from .conversions import from_dict_to_ROS
from .conversions import from_ROS_to_dict
from .conversions import from_JSON_to_ROS
from .conversions import from_ROS_to_JSON
from .conversions import get_ROS_msg_type
from .conversions import get_ROS_class
from .conversions import is_ros_message_installed, is_ros_service_installed
from pydoc import locate
import socket
import json
import traceback
import threading

from .rosbridge_client import ROSBridgeClient
from rosbridge_library.rosbridge_protocol import RosbridgeProtocol




"""
Server to expose locally and externally
topics, services and parameters from a remote
roscore to a local roscore.

Author: Sammy Pfeiffer <Sammy.Pfeiffer at student.uts.edu.au>
"""

yaml_config = '''
# ROSbridge websocket server info
rosbridge_ip: 192.168.1.31
rosbridge_port: 9090
# Topics being published in the robot to expose locally
remote_topics: [ ['/joint_states', 'sensor_msgs/JointState'],
                    ['/tf', 'tf2_msgs/TFMessage'],
                    ['/scan', 'sensor_msgs/LaserScan']
                    ]
# Topics being published in the local roscore to expose remotely
local_topics: [
                    ['/test1', 'std_msgs/String'],
                    ['/closest_point', 'sensor_msgs/LaserScan']
                    ]
# Services running in the robot to expose locally
remote_services: [
                    ['/rosout/get_loggers', 'roscpp/GetLoggers']
                    ]
# Services running locally to expose to the robot
local_services: [
                    ['/add_two_ints', 'beginner_tutorials/AddTwoInts']
                    ]
# Parameters to be sync, they will be polled to stay in sync
parameters: ['/robot_description']
parameter_polling_hz: 1'''

def synchronized(func):	
    func.__lock__ = threading.Lock()
        
    def synced_func(*args, **kws):
        with func.__lock__:
            return func(*args, **kws)

    return synced_func


class ROSductBridge(object):    

    def __init__(self, node_handle):  
        parameters = {
            "fragment_timeout": 600,  # seconds
            "delay_between_messages": 0,  # seconds
            "max_message_size": 10000000,  # bytes
            "unregister_timeout": 10.0,  # seconds
            "bson_only_mode": False,
            # "compression": "cbor",
        }

        try:
            self.protocol = RosbridgeProtocol(
                "TODO_generate_client_ID", parameters
            )
            # self.incoming_queue = IncomingQueue(self.protocol)
            # self.incoming_queue.start()
            self.protocol.outgoing = self.send_message
            # self.set_nodelay(True)
            # self._write_lock = threading.RLock()            
        except Exception as exc:
            node_handle.get_logger().error(
                f"Exception thrown.  Reason: {exc}"
            )
      
        
        # ROSbridge
        self.rosbridge_ip = rospy.get_param('~rosbridge_ip', None)
        if self.rosbridge_ip is None:
            rospy.logerr('No rosbridge_ip given.')
            raise Exception('No rosbridge_ip given.')
        self.rosbridge_port = rospy.get_param('~rosbridge_port', 9090)
        self.wss = rospy.get_param('~use_wss', False)
        rospy.loginfo("Will connect to ROSBridge websocket: {}://{}:{}".format(
            "wss" if self.wss else "ws", self.rosbridge_ip, self.rosbridge_port))

        # Topics
        # TODO: check if topic types are installed, if not, give a warning
        self.remote_topics = rospy.get_param('~remote_topics', [])
        #rospy.loginfo("Remote topics: " + str(self.remote_topics))
        if (rospy.get_param('~all_local_topics', False)):
          self.local_topics = self.get_all_local_topics()
        else:
          self.local_topics = rospy.get_param('~local_topics', [])
          #rospy.loginfo("Local topics: " + str(self.local_topics))

        # Services
        # TODO: check if service types are installed
        self.remote_services = rospy.get_param('~remote_services', [])
        #rospy.loginfo("Remote services: " + str(self.remote_services))
        self.local_services = rospy.get_param('~local_services', [])
        #rospy.loginfo("Local services: " + str(self.local_services))

        # Parameters
        self.rate_hz = rospy.get_param('~parameter_polling_hz', 1)
        self.parameters = rospy.get_param('~parameters', [])
        #rospy.loginfo("Parameters: " + str(self.parameters))
        self.last_params = {}

        self.check_if_msgs_are_installed()

        self.initialize()
        self.expose_local_topic = rospy.Service('~expose_local_topic', ROSDuctConnection, self.add_local_topic)
        self.close_local_topic = rospy.Service('~close_local_topic', ROSDuctConnection, self.remove_local_topic)
        self.expose_local_service = rospy.Service('~expose_local_service', ROSDuctConnection, self.add_local_service)
        self.close_local_service = rospy.Service('~close_local_service', ROSDuctConnection, self.remove_local_service)
        self.expose_remote_topic = rospy.Service('~expose_remote_topic', ROSDuctConnection, self.add_remote_topic)
        self.close_remote_topic = rospy.Service('~close_remote_topic', ROSDuctConnection, self.remove_remote_topic)
        self.expose_remote_service = rospy.Service('~expose_remote_service', ROSDuctConnection, self.add_remote_service)
        self.close_remote_service = rospy.Service('~close_remote_service', ROSDuctConnection, self.remove_remote_service)

    @synchronized
    def send_message(self, message):        
        # rospy.loginfo("This is where a message should be sent")
        # rospy.loginfo("Message is: %s", message)
        if (self.client._connected):
            try:
                self.client.send(message)
            except Exception as e:                
                rospy.logwarn("Exception sending message: %s", e)
                traceback.print_exc()
                rospy.logwarn("Triggering reconnect")
                self.client.reconnect()                
        else:
            rospy.logwarn("Websocket client disconnected, dropping message for now")    

    def initialize(self):
        """
        Initialize creating all necessary bridged clients and servers.
        """

        connected = False
        while not rospy.is_shutdown() and not connected:
            try:
                self.client = ROSBridgeClient(
                    self.rosbridge_ip, self.rosbridge_port, self.wss)
                connected = True
            except socket.error as e:
                rospy.logwarn(
                    'Error when opening websocket, is ROSBridge running?')
                rospy.logwarn(e)
                rospy.sleep(5.0)

        # We keep track of the instanced stuff in this dict
        self._instances = {'topics': [],
                           'services': []}
        for r_t in self.remote_topics:
            if len(r_t) == 2:
                topic_name, topic_type = r_t
                local_name = topic_name
                latch = False
            elif len(r_t) == 3:
                topic_name, topic_type, local_name = r_t
                latch = False
            elif len(r_t) == 4:
                topic_name, topic_type, local_name, latch = r_t

            msg = ROSDuctConnection()
            msg.conn_name = topic_name
            msg.conn_type = topic_type
            msg.alias_name = local_name
            msg.latch = latch if latch.__class__==bool else latch.lower() == 'true'
            self.add_remote_topic(msg)

        for l_t in self.local_topics:
            if len(l_t) == 2:
                topic_name, topic_type = l_t
                remote_name = topic_name
                latch = False
            elif len(l_t) == 3:
                topic_name, topic_type, remote_name = l_t
                latch = False
            elif len(l_t) == 4:
                topic_name, topic_type, remote_name, latch = l_t

            msg = ROSDuctConnection()
            msg.conn_name = topic_name
            msg.conn_type = topic_type
            msg.alias_name = remote_name
            msg.latch = latch if latch.__class__==bool else latch.lower() == 'true'
            self.add_local_topic(msg)

        # Services
        for r_s in self.remote_services:
            if len(r_s) == 2:
                service_name, service_type = r_s
                local_name = service_name
            elif len(r_s) == 3:
                service_name, service_type, local_name = r_s

            msg = ROSDuctConnection()
            msg.conn_name = service_name
            msg.conn_type = service_type
            msg.alias_name = local_name
            self.add_remote_service(msg)

        for l_s in self.local_services:
            if len(l_s) == 2:
                service_name, service_type = l_s
                remote_name = service_name
            elif len(l_s) == 3:
                service_name, service_type, remote_name = l_s

            msg = ROSDuctConnection()
            msg.conn_name = service_name
            msg.conn_type = service_type
            msg.alias_name = remote_name
            self.add_local_service(msg)


        # Get all params and store them for further updates
        for param in self.parameters:
            if type(param) == list:
                # remote param name is the first one
                param = param[0]
            self.last_params[param] = self.client.get_param(param)

    def add_local_topic(self, msg):
        # a local topic means a local subscribe 
        # and an advertise operation
        p_msg = {}
        p_msg["op"] = "advertise"
        p_msg["topic"] = msg.conn_name
        p_msg["type"] = msg.conn_type
        # this advertises the topic remotely
        self.protocol.outgoing(json.dumps(p_msg))
        # this creates the local subscription
        p_msg["op"] = "subscribe"
        #TODO: figure out how to enable compression
        # apparently compression on receiving server side is not yet implemented: 
        # https://github.com/RobotWebTools/rosbridge_suite/issues/635#issuecomment-909898370
        # p_msg["compression"] = "cbor" 
        self.protocol.incoming(message_string=json.dumps(p_msg))

        # bridgepub = self.client.publisher(msg.alias_name,
        #                                   msg.conn_type,
        #                                   latch=msg.latch)

        # cb_l_to_r = self.create_callback_from_local_to_remote(msg.conn_name,
        #                                                       msg.conn_type,
        #                                                       bridgepub)

        # rossub = rospy.Subscriber(msg.conn_name,
        #                           get_ROS_class(msg.conn_type),
        #                           cb_l_to_r)
        # self._instances['topics'].append(
        #     {msg.conn_name:
        #      {'rossub': rossub,
        #       'bridgepub': bridgepub}
        #      })
        # return ROSDuctConnectionResponse()

    def remove_local_topic(self, msg):
        for i, topic in enumerate(self._instances['topics']):
            if msg.conn_name in topic:
                topic[msg.conn_name]['rossub'].unregister()
                topic[msg.conn_name]['bridgepub'].unregister()
                del self._instances['topics'][i]
                break
        return ROSDuctConnectionResponse()

    def add_remote_topic(self, msg):
        # a remote topic means a remote subscribe 
        # and a local publish operation
        p_msg = {}
        p_msg["op"] = "subscribe"
        p_msg["topic"] = msg.conn_name
        # p_msg["compression"] = "cbor"
        # send remote subscription req
        self.protocol.outgoing(json.dumps(p_msg))
        # process internally as local pub
        p_msg["op"] = "publish"
        self.protocol.incoming(message_string=json.dumps(p_msg))

        # rospub = rospy.Publisher(msg.alias_name,
        #                          get_ROS_class(msg.conn_type),
        #                          # SubscribeListener added later
        #                          queue_size=1,
        #                          latch=msg.latch)

        # cb_r_to_l = self.create_callback_from_remote_to_local(msg.conn_name,
        #                                                       msg.conn_type,
        #                                                       rospub)
        # subl = self.create_subscribe_listener(msg.conn_name,
        #                                       msg.conn_type,
        #                                       cb_r_to_l)
        # rospub.impl.add_subscriber_listener(subl)
        # self._instances['topics'].append(
        #     {msg.conn_name:
        #      {'rospub': rospub,
        #       'bridgesub': None}
        #      })
        # return ROSDuctConnectionResponse()

    def remove_remote_topic(self, msg):
        for i, topic in enumerate(self._instances['topics']):
            if msg.conn_name in topic:
                topic[msg.conn_name]['rospub'].unregister()
                del self._instances['topics'][i]
                break
        return ROSDuctConnectionResponse()

    def add_local_service(self, msg):
        rosservprox = rospy.ServiceProxy(msg.conn_name,
                                         get_ROS_class(msg.conn_type,
                                                       srv=True))
        l_to_r_srv_cv = self.create_callback_from_local_to_remote_srv(
            msg.conn_name,
            msg.conn_type,
            rosservprox)
        remote_service_server = self.client.service_server(msg.alias_name,
                                                           msg.conn_type,
                                                           l_to_r_srv_cv)
        self._instances['services'].append(
            {msg.conn_name:
             {'rosservprox': rosservprox,
              'bridgeservserver': remote_service_server}
             })
        return ROSDuctConnectionResponse()

    def remove_local_service(self, msg):
        for i, service in enumerate(self._instances['services']):
            if msg.conn_name in service:
                service[msg.conn_name]['rosservprox'].unregister()
                service[msg.conn_name]['bridgeservserver'].unregister()
                del self._instances['services'][i]
                break
        return ROSDuctConnectionResponse()

    def add_remote_service(self, msg):
        remote_service_client = self.client.service_client(msg.conn_name,
                                                           msg.conn_type)
        r_to_l_serv_cb = self.create_callback_from_remote_to_local_srv(
            remote_service_client,
            msg.conn_name,
            msg.conn_type)
        rosserv = rospy.Service(msg.alias_name,
                                get_ROS_class(msg.conn_type,
                                              srv=True),
                                r_to_l_serv_cb)

        self._instances['services'].append(
            {msg.conn_name:
             {'rosserv': rosserv,
              'bridgeservclient': remote_service_client}
             })
        return ROSDuctConnectionResponse()

    def remove_remote_service(self, msg):
        for i, service in enumerate(self._instances['services']):
            if msg.conn_name in service:
                service[msg.conn_name]['bridgeservserver'].unregister()
                del self._instances['services'][i]
                break
        return ROSDuctConnectionResponse()

    def create_callback_from_remote_to_local(self, topic_name,
                                             topic_type,
                                             rospub):
        # Note: argument MUST be named 'message' as
        # that's the keyword given to pydispatch
        def callback_remote_to_local(message):
            rospy.logdebug("Remote ROSBridge subscriber from topic " +
                           topic_name + ' of type ' +
                           topic_type + ' got data: ' + str(message) +
                           ' which is republished locally.')
            # Only convert and publish with subscribers
            if rospub.get_num_connections() >= 1:
                msg = from_dict_to_ROS(message, topic_type)
                rospub.publish(msg)
        return callback_remote_to_local

    def create_callback_from_local_to_remote(self,
                                             topic_name,
                                             topic_type,
                                             bridgepub):
        def callback_local_to_remote(message):
            rospy.logdebug("Local subscriber from topic " +
                           topic_name + ' of type ' +
                           topic_type + ' got data: ' + str(message) +
                           ' which is republished remotely.')
            dict_msg = from_ROS_to_dict(message)
            if not self.client.terminated:                
                bridgepub.publish(dict_msg)
        return callback_local_to_remote

    def create_subscribe_listener(self,
                                  topic_name,
                                  topic_type,
                                  cb_r_to_l):
        # We create a SubscribeListener that will
        # create a rosbridge subscriber on demand
        # and also unregister it if no one is listening
        class CustomSubscribeListener(rospy.SubscribeListener):
            def __init__(this):
                super(CustomSubscribeListener, this).__init__()
                this.bridgesub = None

            def peer_subscribe(this, tn, tp, pp):
                # Only make a new subscriber if there wasn't one
                if this.bridgesub is None:
                    rospy.logdebug(
                        "We have a first subscriber to: " + topic_name)
                    this.bridgesub = self.client.subscriber(
                        topic_name,
                        topic_type,
                        cb_r_to_l)
                    for idx, topic_d in enumerate(self._instances['topics']):
                        if topic_d.get(topic_name):
                            self._instances['topics'][idx][topic_name]['bridgesub'] = this.bridgesub
                            break

            def peer_unsubscribe(this, tn, num_peers):
                # Unsubscribe if there isnt anyone left
                if num_peers < 1:
                    rospy.logdebug(
                        "There are no more subscribers to: " + topic_name)
                    self.client.unsubscribe(this.bridgesub)
                    this.bridgesub = None
                    # May be redundant if it's actually a reference to this.bridgesub already
                    for idx, topic_d in enumerate(self._instances['topics']):
                        if topic_d.get(topic_name):
                            self._instances['topics'][idx][topic_name]['bridgesub'] = None
                            break
        return CustomSubscribeListener()

    def create_callback_from_remote_to_local_srv(self,
                                                 remote_service_client,
                                                 service_name,
                                                 service_type):
        def callback_from_local_srv_call(request):
            rospy.loginfo("Got a SRV call to " + service_name +
                          " of type " + service_type)
            req_dict = from_ROS_to_dict(request)

            result = {
                'responded': False,
                'response': None
            }

            def cb(success, response):
                result['responded'] = True
                if success:
                    result['response'] = response
            remote_service_client.request(req_dict, cb)
            while not rospy.is_shutdown() and not result['responded']:
                rospy.sleep(0.1)
            if result['response'] is None:
                rospy.logerr('Service call didnt succeed (' + str(service_name) +
                             ' of type ' + str(service_type))
                return None
            return from_dict_to_ROS(result['response'],
                                    service_type + 'Response',
                                    srv=True)
        return callback_from_local_srv_call

    def create_callback_from_local_to_remote_srv(self,
                                                 service_name,
                                                 service_type,
                                                 rosservprox):

        def callback_from_remote_service_call(request):
            ros_req = from_dict_to_ROS(request, service_type + 'Request',
                                       srv=True)
            rospy.loginfo("Waiting for server " + service_name + "...")
            rospy.wait_for_service(service_name)
            # TODO: error handling in services...
            try:
                resp = rosservprox.call(ros_req)
                resp_dict = from_ROS_to_dict(resp)
                return_val=True
            except rospy.ServiceException as exc:
                resp_dict = dict()
                return_val=False
                rospy.logerr("Service did not process request: " + str(exc))

            return return_val, resp_dict

        return callback_from_remote_service_call

    def check_if_msgs_are_installed(self):
        """
        Check if the provided message types are installed.
        """
        for rt in self.remote_topics:
            if len(rt) >= 2:
                topic_type = rt[1]

            if not is_ros_message_installed(topic_type):
                rospy.logwarn(
                    "{} could not be found in the system.".format(topic_type))

        for lt in self.local_topics:
            if len(lt) >= 2:
                topic_type = lt[1]

            if not is_ros_message_installed(topic_type):
                rospy.logwarn(
                    "{} could not be found in the system.".format(topic_type))

        for rs in self.remote_services:
            if len(rs) >= 2:
                service_type = rs[1]

            if not is_ros_service_installed(service_type):
                rospy.logwarn(
                    "{} could not be found in the system.".format(service_type))

        for ls in self.local_services:
            if len(ls) >= 2:
                service_type = ls[1]

            if not is_ros_service_installed(service_type):
                rospy.logwarn(
                    "{} could not be found in the system.".format(service_type))

    @synchronized
    def sync_params(self):
        """
        Sync parameter server in between
        external and local roscore (local changes
        are not forwarded).
        """
        for param in self.parameters:
            if type(param) == list:
                local_param = param[1]
                param = param[0]
            else:
                local_param = param
            # Get remote param
            remote_param = self.client.get_param(param)
            if remote_param != self.last_params[param]:
                rospy.set_param(local_param, remote_param)
                self.last_params[param] = remote_param

    def spin(self):
        """
        Run the node, needed to update the parameter server.
        """
        r = rospy.Rate(self.rate_hz)
        while not rospy.is_shutdown():
            if self.client.terminated: # we've lost the connection
                rospy.logerr("Unexpected disconnect from server, shutting down...")
                rospy.signal_shutdown("We've lost the connection!")
                #del self.client # will this remove all the pub/sub objects?
                #self.client.reconnect()
                #self.initialize()
            self.sync_params()
            r.sleep()

    def get_all_local_topics(self):        
        api_client = rospy.ServiceProxy('/rosapi/topics', Topics)
        publishers_client = rospy.ServiceProxy('/rosapi/publishers', Publishers)
        result = api_client()
               
        topic_descriptors = []
        for i in range(0, len(result.topics)):
            if(result.topics[i] not in ["/rosout", "/clock"]):
                # check if topic has at least one local publisher
                pub_res = publishers_client(result.topics[i])
                if (len(pub_res.publishers) > 0):
                    topic_descriptors.append([result.topics[i], result.types[i]])
        return topic_descriptors

def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    node_handle = rospy.init_node('rosduct_bridge')
    r = ROSductBridge(node_handle)
    r.spin()
