from micropython import const
import machine
import utime
import rp2
import _thread
from array import array

# IOs on the Pico:
# Data:      0-7
# Triacs:      8
# Sol1:        9
# Sol3:       10
# Sol4:       11
# Sol2:       12
# Lamp cols:  13
# Lamp rows:  14
# Zero cross: 15

DEMO=const(0)

# 0: no verbose output, 1: some logs, 2: more verbose logs 
DEBUG=const(1)
DEBUG_NONE=const(0)
DEBUG_SOME=const(1)
DEBUG_VERBOSE=const(2)

# Pins as constants
TRIACS=const(1)
SOL1=const(2)
SOL3=const(4)
SOL4=const(8)
SOL2=const(16)
LCOL=const(32)
LROW=const(64)
ZEROCROSS=const(128)

# Global variables
update_counter=0
max_fifo=0
overflow=0
address_errors=0

if DEBUG:
    cols_detected=0
    rows_detected=0
    fifo_count=0
    fifo_sum=0
    
    DEBUGSIZE = const(2000)
    debugarray = [0]*DEBUGSIZE


lights = bytearray(8)
solenoids=bytearray(4)

running=False
finished=True

# State machines
clockmachine = 0
datamachine = 0
lightmachine = 0

# callback functions for detected changes
lamp_notify = 0
solenoid_notify = 0


# This is a performance hack to replace 8 if statements by a table lookup
# when mapping colums to an 0-7 value
colmapping = bytearray(256)
for i in range(0,255):
    colmapping[i] = -1
for i in range(0,7):
    colmapping[1<<i]=i
    

# Wait for a low/high change on GPIO8-14
# As the "wait" command can only wait for a single pin, we need to poll the stat
# of 8 pin here and then check if these are zero/non-zero
#
# Normally all pins are high. When new data needs to be fetch, one of the pins will go
# to low for about 400ns and the data will fetch on the raising edge.
# This code first waits for all pins to be high, then waits for something that goes to low
# When it goes to low, the data will be pushed. It then waits for the raising edge and
# sends an IRQ to inform the data reader process to read the data
#
# We do not process the zerocrossing signal here as it is completely independent from the
# clocks, active high and overlapping. This has to be sampled completely independent.





p5 = machine.Pin(20, machine.Pin.OUT)
p6 = machine.Pin(21, machine.Pin.OUT)

DATABITS=const(15)
@rp2.asm_pio(autopush=True, push_thresh=DATABITS, fifo_join=rp2.PIO.JOIN_RX, set_init=rp2.PIO.OUT_LOW)
def read_data():
    wrap_target()
    wait(1, irq, 0)
    mov(x,invert(pins))    # To save post-processing time, invert pins in the state machine
    in_(x,DATABITS)
    wrap()


CTLBITS=const(7)
@rp2.asm_pio()
def wait_clock():
    wrap_target()

    label ("allhigh")        # Wait until one of the signals changes to low
    mov(isr,invert(null))    # Reset ISR shift counter, set all bits to 1
    in_(pins,CTLBITS)              # Read 7 bits
    mov(x,invert(isr))       # move these 8 bits (and the other 24) to X
    jmp(x_dec, "allhigh")    # if X is zero, loop again
    mov(isr,x)


    label("isnotzero")       # Now wait until it goes back to H again (should take only 250ns) 
    mov(isr,invert(null))    # Reset ISR shift counter, set all bits to 1
    in_(pins,CTLBITS)              # Read 7 bits
    mov(x,invert(isr))       # move these 7 bits to X and invert it
    jmp(not_x, "isnotzero")  # if X is not zero, try again
    
    nop() [25]               # Wait around 200ns
    irq(0)                   # signal the data reader machine to read the data on the bus
    
    wrap()
    
 
def updateloop():
    global update_counter
    global finished
    global max_fifo
    global overflow
    global address_errors
    if DEBUG:
        global cols_detected
        global rows_detected
        global col0_detected
        global colother_detected
        global debugarray
    
    pindata2=0
    errors=0
    
    lightscol=0
    lightsrow=0
    
    i=0
    
    while running:
    
        lights_updated=0
        solenoids_updated=0
        
        fdata=datamachine.rx_fifo()
        if not fdata:
            continue
        
        if fdata > max_fifo:
            max_fifo=fdata
            if fdata == 8:
                # If the queue is completely filled, there is most likely an overflow
                # We can't be sure at the state machine will just block but it's a bad sign
                overflow = 1
        
        d = datamachine.get()
        pindata = d & 0x7fff
            
        update_counter += 1
    
        data=pindata & 0xff
        address=(pindata >> 8) & 0x7f
 
        if address==LROW:
            if lightscol >=0:
                if DEBUG:
                    rows_detected += 1
                if lights[lightscol] != data:
                    lights[lightscol] = data
                    lights_updated=True
            else:
                continue
            lightscol = -1
            
        elif (address==LCOL):
            
            if data==0:
                continue
            
            lightscol = colmapping[data]
            
            if (lightscol < 0) or (lightscol > 7):
                lightscol = -1
                
            if DEBUG:
                cols_detected += 1

        elif (address==SOL1):
            if data != solenoids[0]:
                solenoids[0]=data
                solenoids_updated=True
        elif (address==SOL2):
            if data != solenoids[1]:
                solenoids[1]=data
                solenoids_updated=True
        elif (address==SOL3):
            if data != solenoids[2]:
                solenoids[2]=data
                solenoids_updated=True
        elif (address==SOL4):
            if data != solenoids[3]:
                solenoids[3]=data
                solenoids_updated=True
        elif (address==TRIACS):
            pass
        elif address==0:
            # this should not happen
            if DEBUG >= DEBUG_VERBOSE:
                print("Ooops, got a 0 address: ",pindata)
            address_errors += 1

        else:
            # this should not happen
            if DEBUG >= DEBUG_VERBOSE:
                print("Ooops, unknown address: ",pindata)
            address_errors += 1
        
        if lights_updated:
            update_counter += 1
            if lamp_notify:
                 lamp_notify()
            if DEBUG >= DEBUG_VERBOSE:
                print("Lights: ",lights)
 
        if solenoids_updated:
            update_counter += 1
            if solenoid_notify:
                 solenoid_notify()
            if DEBUG >= DEBUG_VERBOSE:
                print("Solenoids: ",solenoids)
            
    finished=True
    
class PowerMonitor():

    def __init__(self, gpio_base=0, statemachine_base=0):
        global clockmachine
        global datamachine
        global lightmachine
        
        clockmachine = rp2.StateMachine(statemachine_base,
                                        wait_clock,
                                        in_base=machine.Pin(gpio_base+8))

        datamachine = rp2.StateMachine(statemachine_base+2,
                                       read_data,
                                       in_base=machine.Pin(gpio_base),
                                       out_base=p5)
        
        self.monitor_thread=None

        if DEBUG:
            print ("State machines started")
            

    def set_lamp_notify(self, notify_func):
        global lamp_notify
        lamp_notify = notify_func
        
    def set_solenoid_notify(self, notify_func):
        global solenoid_notify
        solenoid_notify = notify_func
        
    def start(self):
        global running
        global finished
        
        running=True
        finished=False
        
        datamachine.active(1)
        clockmachine.active(1)

        self.monitor_thread=_thread.start_new_thread(updateloop,())
        
        if DEBUG:
            print ("Monitoring thread started")
            

    def stop(self):
        global running
        global finished
        
        running=False
        
        while not finished:
            utime.sleep(0.01)
            
        finished=True
            
        clockmachine.active(0)
        lightmachine.active(0)
        datamachine.active(0)
            
        self.monitor_thread=None
        
        if DEBUG:
            print ("Monitoring thread stopped")

### Some demo code
            
if DEMO:
            
    l_prev = 0
    l_changed = int.from_bytes(lights,'big') # will be 0 at this stage

    s_prev = 0
    s_changed = int.from_bytes(solenoids,'big') # will be 0 at this stage


    lamp_notifications = 0
    solenoid_notifications = 0 

    def lamp_notify_demo():
        global lamp_notifications
        global l_prev
        global l_changed
        
        lamp_notifications += 1
        
        l = int.from_bytes(lights,'big') # will be 0 at this stage
        
        ldiff = l_prev ^ l
        
        l_changed = l_changed | ldiff
        
        l_prev=l
        
    def solenoid_notify_demo():
        global solenoid_notifications
        global s_prev
        global s_changed
        
        solenoid_notifications += 1
        
        return
        
        s = int.from_bytes(solenoids,'big') # will be 0 at this stage
        
        sdiff = s_prev ^ s
        
        s_changed = s_changed | sdiff
        
        s_prev=s

    def dump_debugarray():
        if DEBUG:
            prev_col=False
            for i in range(0,DEBUGSIZE-1):
                d=debugarray[i]
                d2=d & 0xff
                d1=d>>8
                
                if d1==TRIACS:
                    s="Trcs"
                elif d1==SOL1:
                    s="Sol1"
                elif d1==SOL2:
                    s="Sol2"
                elif d1==SOL3:
                    s="Sol1"
                elif d1==SOL4:
                    s="Sol2"
                elif d1==LCOL:
                    s="Lcol"
                    if d2 == 0x01:
                        prev_col=True
                elif d1==LROW:
                    s="Lrow"
                    if prev_col and d2 != 0:
                        print("oops")
                    if prev_col and d2 != 0:
                        print("yeahhh")
                else:
                    s="????"
                    
                if prev_col:
                    print("{0} {1:0>8b} ".format(s,d2))
                    
                if d1==LROW:
                    prev_col=False
        else:
            pass

    def demo():
        global l_prev
        global max_fifo

        i=0
        
        pm = PowerMonitor()
        pm.start()
        utime.sleep(0.1)
        # Read the initial lamp state
        l_prev = int.from_bytes(lights,'big')
        l_initial = l_prev
        
        # Read the initial solenoid state
        s_prev = int.from_bytes(solenoids,'big')
        s_initial = s_prev
        
        pm.set_lamp_notify(lamp_notify_demo)
        pm.set_solenoid_notify(lamp_notify_demo)
        
        while i<100:
            
            print(i)
            
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
        print("Initial solenoids: {0:0>32b}".format(s_initial,))
        print("Solenoids changed: {0:0>32b}".format(s_changed))
        print("Final solenoids:   {0:0>32b}".format(int.from_bytes(solenoids,'big')))
        
    #    dump_debugarray()

    demo()
                 
      
