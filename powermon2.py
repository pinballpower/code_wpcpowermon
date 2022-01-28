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

counters=[0,0,0,0,0,0,0,0,0]
    
clockmachine = rp2.StateMachine(0, wait_clock, in_base=machine.Pin(8))
clockmachine.active(1)

datamachine = rp2.StateMachine(1, read_data, in_base=machine.Pin(0))
datamachine.active(1)


print ("State machine started")

lights = bytearray(8)
sols=bytearray(4)

c=0
t1=utime.ticks_ms()
start=utime.ticks_ms()
running=True
t2=0
address=0

while running:
    was_updated=False
    lights_updates=False
    sols_updated=False
    
    # address=clockmachine.get()
    pindata = ~ datamachine.get()
    data=pindata & 0xff
    address=(pindata >> 8) & 0x7f
    
    c+=1
    if address != 0:
        x=address
        if (x==1):
            counters[0] += 1 
        elif (x==2):
            counters[1] += 1 
        elif (x==4):
            counters[2] += 1 
        elif (x==8):
            counters[3] += 1 
        elif (x==16):
            counters[4] += 1 
        elif (x==32):
            counters[5] += 1 
        elif (x==64):
            counters[6] += 1 
        elif (x==128):
            counters[7] += 1
        else:
            counters[8] += 1
    address=0
    
    t2=utime.ticks_ms()
    diff=utime.ticks_diff(t2,start)
    if diff > 10000:
        print("10s running, aborting")
        running=False
    
    if False:
        c = c+1
    #    print(i)
        d=lightsmachine.get()
        rowcode = (d & 0xff00) >> 8
        r=-1
        if rowcode==0b11111110:
            r=0
        elif rowcode==0b11111101:
            r=1
        elif rowcode==0b11111011:
            r=2
        elif rowcode==0b11110111:
            r=3
        elif rowcode==0b11101111:
            r=4
        elif rowcode==0b11011111:
            r=5
        elif rowcode==0b10111111:
            r=6
        elif rowcode==0b01111111:
            r=7

        if r != -1:
            l=(~d & 0xff)
            if lights[r] != l:
                lights[r] = l
                was_updated=True
                lights_updates=True
                
    if was_updated:
        pass
        #print("Lights: ",lights)
        #print("Solenoids: ", sols)

    if sols_updated:
        print("Solenoids: ", sols)
             
    if c>=1000:
        t2=utime.ticks_ms()
        diff=utime.ticks_diff(t2,t1)
        f=1000000.0/diff
        print(f)
        c=0
        t1=t2
        
print(counters);
        
clockmachine.active(0)
      