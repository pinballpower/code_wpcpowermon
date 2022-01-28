import machine
import utime
import rp2

# Triacs:      8
# Sol1:        9
# Sol3:       10
# Sol4:       11
# Sol2:       12
# Lamp cols:  13
# Lamp rows:  14
# Zero cross: 15

# Wait for a low/high change on GPIO8-15
# As the "wait" command can only wait for a single pin, we need to poll the stat
# of 8 pin here and then check if these are zero/non-zero
#
# Normally all pins are high. When new data needs to be fetch, one of the pins will go
# to low for about 400ns and the data will fetch on the raising edge.
# This code first waits for all pins to be high, then waits for something that goes to low
# When it goes to low, the data will be pushed. It then waits for the raising edge and
# sends an IRQ to inform the data reader process to read the data
#
@rp2.asm_pio()
def wait_clock():
    mov (y, null)
    wrap_target()
    #irq(0)
    label ("allhigh")
    mov(isr,invert(null))    # Reset ISR shift counter
    in_(pins,1)              # Read 8 bits
    mov(x,invert(isr))       # move these 8 bits (and the other 24) to X
    jmp(x_dec, "allhigh")
    mov(isr,x)

    label("isnotzero")
    mov(isr,invert(null))    # Reset ISR shift counter
    in_(pins,1)   # Read 8 bits
    mov(x,invert(isr))    # move these 8 bits to X
    jmp(not_x, "isnotzero") # if X is not zero, try again
    mov(isr,x)
    push()
    irq(0)
    
    wrap()


c=0

counters=[0,0,0,0,0,0,0,0,0]
    
clockmachine = rp2.StateMachine(0, wait_clock, in_base=machine.Pin(13))
clockmachine.active(1)
#clockmachine.irq(counter) #Set the IRQ handler

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
    
    address=clockmachine.get()
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
      