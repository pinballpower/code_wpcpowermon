from powermon import PowerMonitor

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
    
    return
    
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
    
    return
    
    s = int.from_bytes(solenoids,'big') # will be 0 at this stage
    
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
        print("Max FIFO size:", max_fifo)
        max_fifo=0
        
        if DEBUG:
            if fifo_count > 0:
                print("Average FIFO size:", fifo_sum/fifo_count)
            else:
                print("No data")
            
            fifo_sum=0
            fifo_count=0
        
        i += 1        
        utime.sleep(1)
        
    # pm.stop()

    print("Events received from bus: ", update_counter)
    print("Address errors: ",address_errors)
    if overflow:
        print("!!! Overflow detected !!!")
    else:
        print("No overflow detected")

    if DEBUG:
        print("Columns detected: ",cols_detected)
        print("Rows detected: ",rows_detected)

    print("Lamp change notifications: ", lamp_notifications)
    print("Initial lamps:     {0:0>64b}".format(l_initial))
    print("Lamps changed:     {0:0>64b}".format(l_changed))
    print("Final lamps:       {0:0>64b}".format(int.from_bytes(lights,'big')))

    print("Solenoid change notifications: ", solenoid_notifications)
    print("Initial solenoids: {0:0>32b}".format(s_initial))
    print("Solenoids changed: {0:0>32b}".format(s_changed))
    print("Final solenoids:   {0:0>32b}".format(int.from_bytes(solenoids,'big')))
    
    # dump_debugarray_plain()

demo()
           
