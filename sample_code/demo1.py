from powermon_viper import PowerMonitor

DEBUG=const(0)

import utime

pm = None # The power monitor object will be initialized later

lamp_notifications = 0
solenoid_notifications = 0

l_prev = 0
l_changed = 0

s_prev = 0
s_changed = 0

def lamp_notify_demo():
    # Make sure, the notify code is as small as possible. This runs on the same CPU core as the
    # data poller.
    # It should not run for more than 1ms. Otherwise, there might be a buffer overflow in the backend
    global lamp_notifications
    global l_prev
    global l_changed
    
    lamp_notifications += 1
    
    l = pm.get_lights()
    
    ldiff = l_prev ^ l
    
    l_changed = l_changed | ldiff
    
    l_prev=l
    
def solenoid_notify_demo():
    # Make sure, the notify code is as small as possible. This runs on the same CPU core as the
    # data poller.
    # It should not run for more than 1ms. Otherwise, there might be a buffer overflow in the backend

    global solenoid_notifications
    global s_prev
    global s_changed
    
    solenoid_notifications += 1
    
    s = pm.get_solenoids() 
    
    sdiff = s_prev ^ s
    
    s_changed = s_changed | sdiff
    
    s_prev=s

def demo():
    global l_prev
    global max_fifo
    global fifo_count
    global fifo_sum
    global pm

    i=0
    
    pm = PowerMonitor()
    pm.start()
    # Just delay a bit to make sure we get the current state of everything correctly
    utime.sleep(0.1)
    # Read the initial lamp state
    l_prev = pm.get_lights()
    l_initial = l_prev
    
    # Read the initial solenoid state
    s_prev = pm.get_solenoids()
    s_initial = s_prev
    
    pm.set_lamp_notify(lamp_notify_demo)
    pm.set_solenoid_notify(solenoid_notify_demo)
    
    while i<10:
        
        print(i)
        i += 1        
        utime.sleep(1)
        
    print(pm.get_stats())
        
    print("Lamp change notifications: ", lamp_notifications)
    print("Initial lamps:     {0:0>64b}".format(l_initial))
    print("Lamps changed:     {0:0>64b}".format(l_changed))
    print("Final lamps:       {0:0>64b}".format(pm.get_lights()))

    print("Solenoid change notifications: ", solenoid_notifications)
    print("Initial solenoids: {0:0>32b}".format(s_initial))
    print("Solenoids changed: {0:0>32b}".format(s_changed))
    print("Final solenoids:   {0:0>32b}".format(pm.get_solenoids()))

demo()
           
