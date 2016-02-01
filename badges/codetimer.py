""" Simple timer module for timing code execution """

import time

__author__ = "Mike Stabile"

CODE_TIMER = None

class CodeTimer(object):
    '''simple class for placing timers in the code for performance testing'''

    def add_timer(self, timer_name):
        ''' adds a timer to the class '''
        setattr(self, timer_name, [])

    def log(self, timer_name, node):
        ''' logs a event in the timer '''
        timestamp = time.time()
        if hasattr(self, timer_name):
            getattr(self, timer_name).append({
                "node":node,
                "time":timestamp})
        else:
            setattr(self, timer_name, [{"node":node, "time":timestamp}])
    def print_timer(self, timer_name, **kwargs):
        ''' prints the timer to the terminal

            keyword args:
                delete -> True/False  -deletes the timer after printing
        '''
        if hasattr(self, timer_name):
            _delete_timer = kwargs.get("delete", False)
            print("|-------- {} [Time Log Calculation]-----------------|".format(\
                    timer_name))
            print("StartDiff\tLastNodeDiff\tNodeName")
            time_log = getattr(self, timer_name)
            start_time = time_log[0]['time']
            previous_time = start_time
            for entry in time_log:
                time_diff = (entry['time'] - previous_time) *1000
                time_from_start = (entry['time'] - start_time) * 1000
                previous_time = entry['time']
                print("{:.1f}\t\t{:.1f}\t\t{}".format(time_from_start,
                                                      time_diff,
                                                      entry['node']))
            print("|--------------------------------------------------------|")
            if _delete_timer:
                self.delete_timer(timer_name)

    def delete_timer(self, timer_name):
        ''' deletes a timer '''
        if hasattr(self, timer_name):
            delattr(self, timer_name)

def code_timer(reset=False):
    '''Sets a global variable for tracking the timer accross multiple
    files '''

    global CODE_TIMER
    if reset:
        CODE_TIMER = CodeTimer()
    else:
        if CODE_TIMER is None:
            return CodeTimer()
        else:
            return CODE_TIMER
