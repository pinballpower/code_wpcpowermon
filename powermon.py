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

# Read WPC power bus
@rp2.asm_pio()
def read_lights():
    wrap_target()
    wait(0, pin, 13).delay(1)
    wait(1, pin, 13).delay(1)
    in_(pins,8)
    wait(0, pin, 14).delay(1)
    wait(1, pin, 14).delay(1)
    in_(pins,8)
    push()
    wrap()
    
# Read solenoids
@rp2.asm_pio()
def read_sol1():
    wrap_target()
    wait(0, pin, 9).delay(1)
    wait(1, pin, 9).delay(1)
    in_(pins,8)
    push()
    wrap()

lightsmachine = rp2.StateMachine(0, read_lights, in_base=machine.Pin(0))
sol1machine = rp2.StateMachine(1, read_sol1, in_base=machine.Pin(0))

lightsmachine.active(1)
sol1machine.active(1)

print ("State machine started")

lights = bytearray(8)
sols=bytearray(4)

i=0
t1=utime.ticks_ms()
t2=0
while True:
    if lightsmachine.rx_fifo()>=0:
        i = i+1
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
            lights[r]=(~d & 0xff)
        
#    if sol1machine.rx_fifo()>0:
#        i = i+1000
#        sols[0]=(~ sol1machine.get() & 0xff)
#        if (sols[0])>0:
#            i = i+1000
             
    if i>=1000:
        
        t2=utime.ticks_ms()
        diff=utime.ticks_diff(t2,t1)
        f=1000000.0/diff
        print(f)
        print("Lights: ",lights)
        print("Solenoids: ", sols)
        i=0
        t1=t2