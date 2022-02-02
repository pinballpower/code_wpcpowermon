from micropython import const
import machine
import utime
import rp2
import _thread
from array import array
import machine

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

max_fifo=int(0)

overflow=0
address_errors=0

# Thread synchronisation
light_lock    =  _thread.allocate_lock()
solenoid_lock = _thread.allocate_lock()

if DEBUG:
    DEBUGSIZE = const(40)
    debugarray = [0]*DEBUGSIZE
    fifo_count = 0
    fifo_sum = 0
    rows_detected = 0
    cols_detected = 0
    zc_detected = 0
    triacs_detected = 0
    triac_min_time = 0 
    triac_max_time = 0 


lights = bytearray(8)
solenoids = bytearray(4)

running=False
finished=True

# State machines
clockmachine = 0
datamachine = 0
zcmachine = 0

# callback functions for detected changes
lamp_notify = 0
solenoid_notify = 0

# Wait for a low/high change on GPIO8-14
# As the "wait" command can only wait for a single pin, we need to poll the stat
# of 8 pin here and then check if these are zero/non-zero
#
# Normally all pins are high. When new data needs to be fetch, one of the pins will go
# to low for about 400ns and the data will fetch on the raising edge.
# This code first waits for all pins to be high, then waits for something that goes to low
# When it goes to low, the data will be pushed. It then waits 200ns and sends an IRQ to
# inform the data reader process to read the data
#
# We do not process the zerocrossing signal here as it is completely independent from the
# clocks, active high and overlapping. This has to be sampled completely independent.

DATABITS=const(15)
@rp2.asm_pio(autopush=True,
             push_thresh=DATABITS,
             fifo_join=rp2.PIO.JOIN_RX,
             set_init=rp2.PIO.OUT_LOW,
             in_shiftdir=rp2.PIO.SHIFT_LEFT
             )
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
    in_(pins,CTLBITS)        # Read 7 bits
    mov(x,invert(isr))       # move these 8 bits (and the other 24) to X
    jmp(x_dec, "allhigh")    # if X is zero, loop again
    mov(isr,x)


    label("isnotzero")       # Now wait until it goes back to H again (should take only 250ns) 
    mov(isr,invert(null))    # Reset ISR shift counter, set all bits to 1
    in_(pins,CTLBITS)        # Read 7 bits
    mov(x,invert(isr))       # move these 7 bits to X and invert it
    jmp(not_x, "isnotzero")  # if X is not zero, try again
    
    nop() [31]               # Wait around 250ns (at 125MHz, a command runs in 8ns)
                             # This still works if the Pi Pico is overclocked at 250Mhz. In this
                             # case, the data will be samples about 130ns after the falling edge
                             # which still seems to work fine
    irq(0)                   # signal the data reader machine to read the data on the bus
    
    wrap()
 
@rp2.asm_pio()
def wait_zerocrossing():
    wrap_target()
    wait(1,pin,15) [10]
    wait(0,pin,15)
    in_(pins,16)
    push()
    wrap()
    
    
def set_max_fifo(m):
    global max_fifo
    global overflow
    if m == 8:
        # If the queue is completely filled, there is most likely an overflow
        # We can't be sure at the state machine will just block but it's a bad sign
        overflow = 1
    max_fifo=m
    
def found_address_error():
    global address_errors
    address_errors += 1
    
#def set_update_counter(new_value)
    
@micropython.viper
def updateloop():
    global update_counter
    global finished
    
    if DEBUG:
        global rows_detected
        global cols_detected
        global triacs_detected
        global zc_detected
        global fifo_count
        global fifo_sum
        global triac_min_time
        global triac_max_time
        
        lfifo_count = int(0)
        lfifo_sum = int(0)
        lrows_detected = int(0)
        lcols_detected = int(0)
        ltriacs_detected = int(0)
        lzc_detected = int(0)
        ltriac_min_time = int(10000)
        ltriac_max_time = int(0)
        


    # Cache some global objects
    llock =  light_lock
    slock =  solenoid_lock
    ldatamachine = datamachine
    lzcmachine = zcmachine
    
    llights = ptr8(lights)
    lsolenoids = ptr8(solenoids)
    
    triac0 = int(0)
    triac1 = int(0)
    triac2 = int(0)
    triac3 = int(0)
    triac4 = int(0)


    # This is a performance hack to replace 8 if statements by a table lookup
    # when mapping colums to an 0-7 value
    colmapping = ptr8(bytearray(256))
    for i in range(0,255):
        colmapping[i] = -1
    for i in range(0,7):
        colmapping[1<<i]=i
    
    pindata=int(0)
    fdata=int(0)
    zc=int(0)
    lfifo_count=int(0)
    lmax_fifo=int(0)
    lupdate_counter=int(0)
    
    lightscol=int(0)
    lightsrow=int(0)
    
    zctime=int(0)
    triac_set=int(0)
    
    i=0
    
    while running:
    
        lights_updated=0
        solenoids_updated=0
        
        # Check zero crossing first
        fdata=int(lzcmachine.rx_fifo())
        if fdata:
            # Zerocrossing detected, just clean queue, data
            # are not interesting
            zctime=int(utime.ticks_us())

            lzcmachine.get()
            if DEBUG:
                lzc_detected += 1
                zc_detected=lzc_detected
        
        fdata=int(ldatamachine.rx_fifo())
        if not fdata:
            continue
        
        if DEBUG:
            lfifo_count += 1
            lfifo_sum += fdata
            fifo_count=lfifo_count
            fifo_sum=lfifo_sum
        
        if fdata > lmax_fifo:
            lmax_fifo=fdata
            set_max_fifo(lmax_fifo)

            
        d = int(ldatamachine.get())
        pindata = d & 0x7fff
            
        lupdate_counter += 1
        
        data=pindata & 0xff
        address=pindata >> 8
        zc=address>>7
        address=address & 0x7f
 
        if address==LROW:
            if lightscol >=0:
                if DEBUG:
                    lrows_detected += 1
                    rows_detected=lrows_detected
                if llights[lightscol] != data:
                    llock.acquire()
                    llights[lightscol] = data
                    llock.release()
                    lights_updated=1
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
                lcols_detected += 1
                cols_detected=lcols_detected

        elif (address==SOL1):
            if data != lsolenoids[0]:
                slock.acquire()
                lsolenoids[0]=data
                slock.release()
                solenoids_updated=1
        elif (address==SOL2):
            if data != lsolenoids[1]:
                slock.acquire()
                lsolenoids[1]=data
                slock.release()
                solenoids_updated=1
        elif (address==SOL3):
            if data != lsolenoids[2]:
                slock.acquire()
                lsolenoids[2]=data
                slock.release()
                solenoids_updated=1
        elif (address==SOL4):
            if data != lsolenoids[3]:
                slock.acquire()
                lsolenoids[3]=data
                slock.release()
                solenoids_updated=1
        elif (address==TRIACS):
            if DEBUG:
                ltriacs_detected += 1
                triacs_detected=ltriacs_detected
                
                # Only do something if zero crossing is set
                if zctime:
                    ttime=int(utime.ticks_us())
                    
                    
                    # Values are between 0 and about 10000 (0 to 10ms)
                    diff=int(ttime-zctime)
                    triac_set=0
                    
                    triacs = data # Store as we will need it when zero-cross is detected
                    
                    
                    # WPC has 5 triacs, WPC95 only 3
                    if (data & 0x01) and not triac0:
                        triac0 = diff
                        triac_set=1
                    if (data & 0x02) and not triac1:
                        triac1 = diff
                        triac_set=1
                    if (data & 0x04) and not triac2:
                        triac1 = diff
                        triac_set=1
                    if (data & 0x08) and not triac3:
                        triac1 = diff
                        triac_set=1
                    if (data & 0x10) and not triac4:
                        triac1 = diff
                        triac_set=1
                        
                    if DEBUG and triac_set:
                        if diff < ltriac_min_time:
                            ltriac_min_time=diff
                            triac_min_time=ltriac_min_time
                        if diff > ltriac_max_time:
                            ltriac_max_time=diff
                            triac_max_time=ltriac_max_time
                        
                
            pass
        elif address==0:
            # this should not happen
            if DEBUG >= DEBUG_VERBOSE:
                print("Ooops, got a 0 address: ",pindata)
            found_address_error()

        else:
            # this should not happen
            if DEBUG >= DEBUG_VERBOSE:
                print("Ooops, unknown address: ",pindata)
            found_address_errors()
        
        if lights_updated:
            lupdate_counter += 1
            update_counter = lupdate_counter
            if lamp_notify:
                 lamp_notify()
            if DEBUG >= DEBUG_VERBOSE:
                print("Lights: ",lights)
 
        if solenoids_updated:
            lupdate_counter += 1
            update_counter = lupdate_counter
            if solenoid_notify:
                 solenoid_notify()
            if DEBUG >= DEBUG_VERBOSE:
                print("Solenoids: ",solenoids)
                
    finished=True
    
class PowerMonitor():

    def __init__(self, gpio_base=0, statemachine_base=0):
        global clockmachine
        global datamachine
        global zcmachine
        
        clockmachine = rp2.StateMachine(statemachine_base,
                                        wait_clock,
                                        in_base=machine.Pin(gpio_base+8))

        datamachine = rp2.StateMachine(statemachine_base+1,
                                       read_data,
                                       in_base=machine.Pin(gpio_base))
        
        zcmachine = rp2.StateMachine(statemachine_base+2,
                                       wait_zerocrossing,
                                       in_base=machine.Pin(gpio_base))
        
        self.monitor_thread=None

        if DEBUG:
            print ("State machines started")
            

    def set_lamp_notify(self, notify_func):
        global lamp_notify
        lamp_notify = notify_func
        
    def set_solenoid_notify(self, notify_func):
        global solenoid_notify
        solenoid_notify = notify_func
        
    def get_lights(self):
        light_lock.acquire()
        res=int.from_bytes(lights,'big')
        light_lock.release()
        return res
        
    def get_solenoids(self):
        light_lock.acquire()
        res=int.from_bytes(solenoids,'big')
        light_lock.release()
        return res
        
        
    def start(self):
        global running
        global finished
        
        running=True
        finished=False
        
        datamachine.active(1)
        clockmachine.active(1)
        zcmachine.active(1)

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
        zcmachine.active(0)
        datamachine.active(0)
            
        self.monitor_thread=None
        
        if DEBUG:
            print ("Monitoring thread stopped")
            
    def get_stats(self):
        
        if DEBUG:
            return {
                "max_fifo": max_fifo,
                "update_counter": update_counter,
                "overflow": overflow,
                "address_errors": address_errors,
                "rows_detected": rows_detected,
                "cols_detected": cols_detected,
                "zc_detected": zc_detected,
                "triacs_detected": triacs_detected,
                "triac_min_time": triac_min_time,
                "triac_max_time": triac_max_time,
                }
        else:
            return {
                "max_fifo": max_fifo,
                "update_counter": update_counter,
                "overflow": overflow,
                "address_errors": address_errors,
                }
    
    def get_overflow(self):
        return overflow
    
    def reset_overflow(self):
        global overflow
        overflow=0

if __name__ == '__main__':
    pm=PowerMonitor()
    pm.start()
    utime.sleep(2)
    print(pm.get_stats())
