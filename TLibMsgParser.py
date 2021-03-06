from LogParser import LogParser
import re, sys
from datetime import datetime
#from logger import submitter
import logging

class TLibMsgParser(LogParser):
    # static vars

    # beginning of a TLib message distributed by a TServer
    # @16:45:24.5939 [0] 8.1.101.25 distribute_event: message EventReleased
    # or
    # @16:45:24.5942 [0] 8.1.101.25 distribute call/party event: message EventCallPartyDeleted
    # or
    # @16:45:25.1041 [0] 8.1.101.25 send_to_client: message EventACK
    pattern_tlib_msg = re.compile(': message (\S+)$')

    # requests look like this...
    # 2015-05-29T12:21:16.438 Trc 04541 RequestQueryCall received from [66] (00000e85 CIMplicity_EUW1_L2 10.51.167.61:49280)
    # message RequestQueryCall
    pattern_tlib_req_received = re.compile('^(\S+) Trc 04541 (\S+).+\((.+)\)') #(\S+) received .+\((\.+)\)$')
    # OR 
    # @12:21:16.4386 [BSYNC] Trace: Send to backup (SIPS_sg01_B) [20]:
    # message RequestSetCallInfo
    pattern_tlib_req = re.compile('^message (Request\S+)$')
    # ConnID ...
    # pattern_tlib_conn_id = re.compile('\tAttributeConnID\t(\S+)$')
    pattern_tlib_conn_id = re.compile('^\tAttributeConnID\t([0-9a-f]+)$')
    # ThisDN
    pattern_tlib_this_dn = re.compile('^\tAttributeThisDN\t\'(\S+)\'$')
    # Errors...
    # @23:16:17.4586 [0] 8.1.101.33 send_to_client: message EventError
    #     (DN is not configured in CME)
    #     AttributeEventSequenceNumber    00000000010c9288
    #     AttributeTimeinuSecs    458658
    #     AttributeTimeinSecs    1439853377 (23:16:17)
    #     AttributeErrorCode    59
    #     AttributeErrorMessage    'DN is not configured in CME'
    #     ...
    #     AttributeThisDN    '0091BAFE-5E73-1473-97EF-443C330AAA77'
    #     AttributeClientID    1145
    # 2015-08-17T23:16:17.458 Int 04545 Interaction message "EventError" sent to 24 ("ICON_localdb")
    # 2015-08-17T23:16:17.458 Trc 04542 EventError sent to [24] (00000479 ICON_localdb 10.51.60.68:59022)    
 
     
    def __init__(self,submitter,tags={}):
        logging.debug("TLibMsgParser __init__")
        LogParser.__init__(self, submitter,tags)
        # buffer
        self.tlib_msg = ''
        # dictionary for SIP msg
        self.d_tlib_msg = {}
        # bool we are in sip msg
        self.in_tlib_msg = 0
        self.has_ConnID = False
        self.has_ThisDN = False

        
    def init_tlib_message(self):
        self.in_tlib_msg = 1
        self.tlib_msg = ''
        self.has_ConnID = False
        self.has_ThisDN = False
        self.d_tlib_msg.clear()
        self.d_tlib_msg = self.d_common_tags.copy()
        return
    
    def submit_tlib_message(self):
        #print "-- end of TLib msg"
        self.d_tlib_msg['message'] = self.tlib_msg
        self.submitter.d_submit(self.d_tlib_msg,"TLib")        
        self.in_tlib_msg = 0
        return
    
    def parse_line(self, line, claimed=False):
        # print line
        # submit if we are in.
        if(claimed):
            if(self.in_tlib_msg):
                self.submit_tlib_message()
            else: # TLib request is a StdLib message that may be claimed
                # logging.debug("checking for TLib req in line "+ line)
                self.re_line = self.pattern_tlib_req_received.match(line)
                if(self.re_line):
                    # logging.debug("matched TLib req in "+line)
                    self.match_time_stamp(self.re_line.group(1))
                    self.init_tlib_message()
                    self.d_tlib_msg['method'] = self.re_line.group(2)                      
                    self.d_tlib_msg['from'] = self.re_line.group(3)                      
                    self.d_tlib_msg['@timestamp'] = datetime(self.cur_date['y'],self.cur_date['m'],self.cur_date['d'],self.cur_time['h'],self.cur_time['m'],self.cur_time['s'],self.cur_time['ms'])
                        
                    return True
                    
            return False
        # are we in the part of the TLib log that is a TLib Message?
        if(self.in_tlib_msg):
            self.in_tlib_msg += 1
            # Conn ID?
            if not self.has_ConnID:
                _re_conn_id = self.pattern_tlib_conn_id.match(line)
                if(_re_conn_id):
                    self.has_ConnID = True
                    self.d_tlib_msg['ConnID'] = _re_conn_id.group(1).rstrip()
            if not self.has_ThisDN:
                _re_this_dn = self.pattern_tlib_this_dn.match(line)
                if(_re_this_dn):
                    self.has_ThisDN = True 
                    self.d_tlib_msg['ThisDN'] = _re_this_dn.group(1).rstrip()       
            #    # checking for the end, and sending

            # in most cases TLib message attributes start with a \t - tab
            # if we are in a TLib message and see a \t we'll just add the line and go on
            if(line[0] != '\t'):
                #and we'll be expecting a timestamp after the TLib message ends
                if(self.match_time_stamp(line)):
                    self.submit_tlib_message()
                    # another TLib message can begin right here, therefore need to parse this line
                    return self.parse_line(line)
            #    #else:

            self.tlib_msg = self.tlib_msg + line
            return True
        
        # we are not, looking for the beggining of the TLib Message  
        else:
            # TLib requests...
            _re_tlib_req = self.pattern_tlib_req.match(line)
            if(_re_tlib_req):
                self.init_tlib_message()
                self.tlib_msg = self.tlib_msg + line
                self.d_tlib_msg['method'] = _re_tlib_req.group(1)  
                self.d_tlib_msg['@timestamp'] = datetime(self.cur_date['y'],self.cur_date['m'],self.cur_date['d'],self.cur_time['h'],self.cur_time['m'],self.cur_time['s'],self.cur_time['ms'])
                
                return True
            # scout for time stamps
            if(line[0] in self.timestamp_begin):
                if(self.match_time_stamp(line)):
                    self.re_line = self.pattern_tlib_msg.search(line) # (line[self.match_result.end():])
                    if(self.re_line):
                        self.init_tlib_message()
                        self.tlib_msg = self.tlib_msg + line
                        self.d_tlib_msg['method'] = self.re_line.group(1)                      
                        self.d_tlib_msg['@timestamp'] = datetime(self.cur_date['y'],self.cur_date['m'],self.cur_date['d'],self.cur_time['h'],self.cur_time['m'],self.cur_time['s'],self.cur_time['ms'])
                    
                        return True
                    
        return False

    def __del__(self):
        logging.debug("TLibSMsgParser __del__")
        if(self.in_tlib_msg):
            self.submit_tlib_message()
        LogParser.__del__(self)
        return