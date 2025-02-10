#!/usr/bin/env python3

import rospy
from rospkg import RosPack

import os, sys, time
import json

from ltrp_config_ros.msg import *
from std_msgs.msg import UInt8
from playsound import playsound

import threading

rp = RosPack()


class Broadcaster:
    def __init__(self, root_dir, debug, self_pkg_name):
        self.DEBUG = debug
        self.err_code = 2
        self.node_name = "BROADCAST"
        self.node_code = None
        self.operation = True
        self.rate1 = rospy.Rate(20)
        self.rate2 = rospy.Rate(20)
        self.system_ready = 9
        
        self.error_code_list_dir = root_dir + '/config/error_code_list.json'
        self.parameter_dir = root_dir + '/config/parameters.json'
        self.topic_list_dir = root_dir + '/config/topic_list.json'
        
        self.error_code_list = None
        self.parameters = None
        self.topic_list = None
        
        # Broadcast
        self.sound_file_dir = rp.get_path(self_pkg_name) + '/config/sound_files/'
        self.SOUND_FILE_CODES = None
        self.SOUND_FILE_LIST = None
        
        self.broadcast_request = None
        self.on_air_flag = False
        self.repeat_flag = False
        
        self.NODE_CODES = None
        self.COMMON_DEFAULT_VALUES = None
        self.DEFAULT_VALUES = None
        self.SYSTEM_SHUTDOWN_CODE = None
        self.REMOTE_CONTROL_COMMAND = None
        
        self.NODE_STATE_ERROR = 9
        self.NODE_STATE_OFFLINE = None
        self.NODE_STATE_ONLINE = None
        
        self.broadcast_topic = None
        self.error_topic = '/ltrp/error'
        self.node_respawn_result_topic = '/ltrp/respawn_result'
        self.remote_control_topic   = None
        self.system_shutdown_topic = None
        self.system_status_topic = None
        self.vital_topic = None
        
        self.boradcast_sub = None
        self.remote_control_sub = None
        self.system_shutdown_sub = None
        self.system_status_sub = None
        
        self.broadcast_pub = None
        self.error_pub = rospy.Publisher(self.error_topic, Error, queue_size=10)
        self.node_respawn_result_pub = rospy.Publisher(self.node_respawn_result_topic, NodeRespawnResult, queue_size=10)
        self.vital_pub = None
        
        
        self.info_msg_broadcast_flag        = 0 # 0: brfore rotation / before broadcasting
                                                # 1: on rotation     / before broadcasting
                                                # 2: rotation_done   / before broadcasting
                                                # 3: rotation done   / on broadcasting 
                                                # 4: rotation_done   / broadcasting done
                                                # 5: on rotation     / broadcasting done
                                                # 6: rotation done   / broadcasting done
                                                
        self.lock = threading.Lock()
        
        self.broadcast_thread = None
        self.communication_thread = threading.Thread(target=self.communication_task, args=())
        
    def raise_error(self, error_code, exception=None):
        self.err_code = error_code
        self.system_ready = self.NODE_STATE_ERROR
        
        if exception is None:
            rospy.logerr('[{}] Error code: {} - {}'.format(self.node_name,
                                                           self.err_code,
                                                           self.error_code_list["{}".format(self.error_code)]))
        else:
            rospy.logerr('[{}] Error code: {} - {}'.format(self.node_name,
                                                           self.err_code,
                                                           exception))
            
        self.operation = False
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        
        self.publish_response()
        self.publish_error_msg()
        
    def load_error_code_list(self):
        try:
            with open(self.error_code_list_dir) as f:
                self.error_code_list = json.loads(f.read())
            return True
        except Exception as e:
            rospy.logerr('[{}] Error {}'.format(self.node_name, e))
            self.raise_error(2, "Error code list loading failed.")
            return False
        
    def load_parameters(self):
        try:
            with open(self.parameter_dir) as f:
                parameters = json.loads(f.read())
            self.NODE_CODES = parameters["NODE_CODE"]["VALUE"]
            self.node_code = self.NODE_CODES[self.node_name]
            self.COMMON_DEFAULT_VALUES = parameters["DEFAULT_VALUES"]["COMMON"]["VALUE"]
            self.DEFAULT_VALUES = parameters[self.node_name]["VALUE"]
            self.REMOTE_CONTROL_COMMAND = parameters["REMOTE_CONTROL_COMMAND"]["VALUE"]
            self.SOUND_FILE_LIST = parameters["BROADCAST_SOUND_LIST"]["FILE_NAME"]
            self.SOUND_FILE_CODES = parameters["BROADCAST_SOUND_LIST"]["VALUE"]
            
            self.set_default_values()
            return True
        
        except Exception as e:
            rospy.logerr('[{}] Error: {}'.format(self.node_name, e))
            self.raise_error(self.error_code_list["ERR_PARAMETER_LOADING_FAILED"])
            return False
        
    def load_topic_list(self):
        try:
            with open(self.topic_list_dir) as f:
                self.topi_list = json.loads(f.read())
                
                self.set_topic()
                self.set_subscriber()
                self.set_publisher()
                return True
        except Exception as e:
            rospy.logerr('[{}] Error: {}'.format(self.node_name, e))
            self.raise_error(self.error_code_list["ERR_TOPIC_LIST_LOADING_FAILED"])
            return False
        
    def set_default_values(self):
        self.err_code = self.COMMON_DEFAULT_VALUES["DEFAULT_ERR_CODE"]
        self.NODE_STATE_ERROR = self.COMMON_DEFAULT_VALUES["NODE_STATE_ERROR"]
        self.NODE_STATE_OFFLINE = self.COMMON_DEFAULT_VALUES["NODE_STATE_OFFLINE"]
        self.NODE_STATE_ONLINE = self.COMMON_DEFAULT_VALUES["NODE_STATE_ONLINE"]
        self.SYSTEM_SHUTDOWN_CODE = self.COMMON_DEFAULT_VALUES["SYSTEM_SHUTDOWN_CODE"]
        
    def set_publisher(self):
        self.broadcast_pub = rospy.Publisher(self.broadcast_topic, Broadcast, queue_size=10)
        self.vital_pub = rospy.Publisher(self.vital_topic, Vital, queue_size=10)
        
    def set_subscriber(self):
        self.broadcast_sub = rospy.Subscriber(self.broadcast_topic, Broadcast, self.broadcast_callback)
        self.remote_control_sub = rospy.Subscriber(self.remote_control_topic, UInt8, self.remote_control_callback)    
        self.system_shutdown_sub = rospy.Subscriber(self.system_shutdown_topic, UInt8, self.system_shutdown_callback)
        self.system_status_sub = rospy.Subscriber(self.system_status_topic, SystemStatus, self.system_status_callback)
        
    def set_topic(self):
        prefix = self.topic_list["prefix"]
        self.broadcast_topic = prefix + self.topic_list["broadcast_topic"]["NAME"]
        self.remote_control_topic = prefix + self.topic_list["remote_control_topic"]["NAME"]
        self.system_shutdown_topic = prefix + self.topic_list["system_shutdown_topic"]["NAME"]
        self.system_status_topic = prefix + self.topic_list["system_status_topic"]["NAME"]
        self.vital_topic = prefix + self.topic_list["vital_topic"]["NAME"]
    
    def broadcast_callback(self, msg: Broadcast):
        if msg.NodeCode == self.NODE_CODES["DRIVE_CONTROL"]:
            if msg.MsgCode in self.SOUND_FILE_CODES:
                if not self.on_air_flag:
                    self.broadcast_request = msg.MsgCode
                    sound_file_name = self.sound_file_dir + self.SOUND_FILE_LIST["{}".format(self.broadcast_request)]
                    if msg.MsgCode == self.SOUND_FILE_CODES["ALARM_SOUND"]:
                        self.repeat_flag = True
                    self.broadcast_thread = threading.Thread(target=self.broadcast_task, args=(sound_file_name))
                    self.broadcast_thread.start()
                    self.on_air_flag = True
                else:
                    if msg.MsgCode == self.SOUND_FILE_CODES["CANCLE_BROADCASTING"]:
                        self.broadcast_thread.join()
                        self.broadcast_thread = None
    
    def remote_control_callback(self, msg: UInt8):
        if msg.data == self.REMOTE_CONTROL_COMMAND["REMOTE_PLAY_TEST_SOUND"]:
            if not self.on_air_flag:
                self.broadcast_request = self.SOUND_FILE_CODES["TEST_SOUND"]
                sound_file_name = self.sound_file_dir + self.SOUND_FILE_LIST["{}".format(self.broadcast_request)]
                self.repeat_flag = True
                self.on_air_flag = True
                self.broadcast_thread = threading.Thread(target=self.broadcast_task, args=(sound_file_name))
                self.broadcast_thread.start()
        elif msg.data == self.REMOTE_CONTROL_COMMAND["REMOTE_STOP_PLAYING_SOUND"]:
            if self.on_air_flag:
                self.broadcast_thread.join()
                self.broadcast_thread = None
            
    def system_shutdown_callback(self, msg: UInt8):
        if msg.data in [self.SYSTEM_SHUTDOWN_CODE, self.node_code]:
            self.lock.acquire()
            self.operation = False
            self.shutdown_flag = True
            self.lock.release()
    
    def publish_error_msg(self):
        msg = Error()
        msg.NodeCode = self.node_code
        msg.ErrorCode = self.err_code
        msg.Description = self.error_code_list["{}".format(self.err_code)]
        
        self.error_pub.publish(msg)
        
    def publish_response(self):
        msg = NodeRespawnResult()
        msg.header.stamp = rospy.Time.now()
        msg.NodeCode = self.node_code
        msg.Result = self.system_ready
        
        self.node_respawn_result_pub.publish(msg)
        
    def publish_vital_chk_msg(self):
        try:
            msg = Vital()
            msg.NodeCode = self.node_code
            msg.State = self.system_ready
            msg.ErrorCode = self.err_code
            
            self.vital_pub.publish(msg)
            
        except Exception as e:
            self.raise_error(self.error_code_list["ERR_MAL_FUNCTION"])
    
    def communication_task(self):
        op = True
        rospy.loginfo('[{}] Node started.'.format(self.node_code))
        try:
            while op:
                op = self.operation
                
                self.rate1.sleep()
        finally:
            if self.shutdown_flag:
                self.broadcast_request = self.SOUND_FILE_CODES["SHUT_DOWN_MSG"]
                sound_file_name = self.sound_file_dir + self.SOUND_FILE_LIST["{}".format(self.broadcast_request)]
                self.on_air_flag = True
                self.broadcast_thread = threading.Thread(target=self.broadcast_task, args=(sound_file_name))
                self.broadcast_thread.start()
                
                on_air_flag  = True
                while on_air_flag:
                    time.sleep(0.05)
                    self.lock.acquire()
                    on_air_flag = self.on_air_flag
                    self.lock.release()
                    
            if self.broadcast_thread.is_alive():
                self.broadcast_thread.join()
            self.system_ready = self.NODE_STATE_OFFLINE
            self.publish_response()
            rospy.loginfo('[{}] Node terminated.'.format(self.node_code))
            
    def broadcast_task(self, sound_file_name):
        repeat_flag = True
        rospy.loginfo('[{}] Start playing sound: {}'.format(self.node_code, 
                                                            self.broadcast_request))
        try:
            while repeat_flag:
                playsound(sound_file_name)
                self.lock.acquire()
                repeat_flag = self.repeat_flag
                self.lock.release()
        finally:
            rospy.loginfo('[{}] Stop playing sound.'.format(self.node_name))
            self.lock.acquire()
            self.repeat_flag = False
            self.on_air_flag = False
            self.lock.release()
            
    def run(self):
        try:
            self.communication_thread.start()
        finally:
            if self.communication_thread.is_alive():
                self.communication_thread.join()
            
                
if __name__ == '__main__':
    rospy.init_node('broadcaster', anonymous=False)
    
    root_pkg = "ltrp_config_ros"
    debug = False
    
    if rospy.has_param('root_pkg'):
        root_pkg = rospy.get_param('root_pkg')
    
    if rospy.has_param('debug'):
        debug = rospy.get_param('debug')
        
    root_dir = rp.get_path(root_pkg)
    
    node = Broadcaster(
        root_dir=root_dir,
        debug=debug,
        self_package_name="ltrp_broadcast_ros"
    )
    
    node.run()


