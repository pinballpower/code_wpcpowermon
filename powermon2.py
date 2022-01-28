from micropython import const
import machine
import utime
import rp2

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

# Pins as constants
TRIACS=const(1)
SOL1=const(2)
SOL3=const(4)
SOL4=const(8)
SOL2=const(16)
LCOL=const(32)
LROW=const(64)
ZEROCROSS=const(128)

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
#
@rp2.asm_pio()
def read_data():
    wrap_target()
    wait(1, irq, 0)
    in_(pins,15)
    push()
    wrap()


@rp2.asm_pio()
def wait_clock():
    wrap_target()

    label ("allhigh")        # Wait until one of the signals changes to low
    mov(isr,invert(null))    # Reset ISR shift counter, set all bits to 1
    in_(pins,7)              # Read 7 bits
    mov(x,invert(isr))       # move these 8 bits (and the other 24) to X
    jmp(x_dec, "allhigh")    # if X is zero, loop again
    mov(isr,x)

    label("isnotzero")       # Now wait until it goes back to H again (should take only 250ns) 
    mov(isr,invert(null))    # Reset ISR shift counter, set all bits to 1
    in_(pins,7)              # Read 7 bits
    mov(x,invert(isr))       # move these 7 bits to X and invert it
    jmp(not_x, "isnotzero")  # if X is not zero, try again

    irq(0)                   # signal the data reader machine to read the data on the bus
    
    wrap()


c=0

clockmachine = rp2.StateMachine(0, wait_clock, in_base=machine.Pin(8))
clockmachine.active(1)

datamachine = rp2.StateMachine(1, read_data, in_base=machine.Pin(0))
datamachine.active(1)

print ("State machines started")

lights = bytearray(8)
sols=bytearray(4)

# This is a performance hack to replace 8 if statements by a table lookup
# when mapping colums to an 0-7 value
colmapping = bytearray(256)
for i in range(0,7):
    colmapping[1<<i]=i
    

c=0
t1=utime.ticks_ms()
start=utime.ticks_ms()
running=True
t2=0
address=0
lightscol=0
lightsrow=0

update_counter = 0

while running:
    lights_updated=False
    sols_updated=False
    
    pindata = ~ datamachine.get()
    data=pindata & 0xff
    address=(pindata >> 8) & 0x7f

    if address==0:
        # this should not happen
        #print("Ooops, got a 0 address")
        pass
    elif (address==LCOL):
        lightsrow = colmapping[data]
    elif (address==LROW):
        if lightsrow >=0:
            if lights[lightsrow] != data:
                lights[lightsrow] = data
                lights_updated=True
                # Make sure we ignore the next requests at the end of each
                # column cycle
                lightsrow = -1
    elif (address==SOL1):
        if data != sols[0]:
            sols[0]=data
            sols_updated=True
    elif (address==SOL2):
        if data != sols[1]:
            sols[1]=data
            sols_updated=True
    elif (address==SOL3):
        if data != sols[2]:
            sols[2]=data
            sols_updated=True
    elif (address==SOL4):
        if data != sols[3]:
            sols[3]=data
            sols_updated=True
    elif (address==TRIACS):
        pass
    else:
        print("Ooops, unknown address ",address)
    
    t2=utime.ticks_ms()
    diff=utime.ticks_diff(t2,start)
    if diff > 10000:
        print("10s running, aborting")
        running=False
    
    # Debug code
    if lights_updated:
    #    print("Lights: ",lights)
        update_counter += 1

    if sols_updated:
        print("Solenoids: ", sols)
        

print(update_counter)
    
             
clockmachine.active(0)
datamachine.active(0)
      