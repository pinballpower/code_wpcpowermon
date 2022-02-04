from machine import Pin, PWM, Timer
import utime

PWM_OFF = const(0)              # Output nothing
PWM_SINGLESHOT = const(1)       # Play the effect once and turn off
PWM_RAMP = const(2)             # Play the effect once and let the last effect sample running
PWM_CYCLIC = const(3)           # Cycle the effect
PWM_BACKANDFORTH = const(4)     # Cycle forward/backward through the effect
PWM_RAMPDOWN = const(5)         # Play the effect backward once

def pwm_update(p):
    p.update_data()
    
class PWMEffect():
    
    def __init__(self, pin, pwm_freq=1000, update_ms=10000):
        self.pwm = PWM(pin)
        self.pwm.freq(pwm_freq)
        self.pwm.duty_u16(0)
        
        self.effectlen=0
        self.effect=bytearray(0)
        self.effectcounter=0
        self.effectdir=0
        self.update_ms=update_ms
        self.datadir=0
        self.timer=None
        
    def play_effect(self, data, datalen, mode=PWM_OFF):
        self.effectcounter = 0
        self.effect=data
        self.effectlen=datalen
        self.effectmode=mode
        self.start_effecttimer()
        
    def start_effecttimer(self):
        self.timer = Timer(period=self.update_ms,
                           mode=Timer.PERIODIC,
                           callback=lambda x : pwm_update(self))
        
        
    def stop_effect(self, shutdown=True, rampdown=False):
        if self.timer is not None:
            self.timer.deinit()
            
        if rampdown:
            if self.effectcounter >= self.effectlen:
                self.effectcounter >= self.effectlen-1
            self.effectmode=PWM_RAMPDOWN
            self.start_effecttimer()
        elif shutdown:
            self.pwm.duty_u16(0)
        
    def update_effectcounter(self, c):
        self.effectcounter = c
        
    def update_datadir(self, datadir):
        self.datadir = datadir
        
    @micropython.viper
    def update_data(self):
        if self.effectlen:
            
            ec = int(self.effectcounter)
            el = int(self.effectlen)
            effectmode = int(self.effectmode)
            effect = ptr8(self.effect)
            done = int(0)
            
            if ec <= el-1: 
                # Scale to 16 bit
                self.pwm.duty_u16(effect[ec]*256)
            
            if effectmode == PWM_SINGLESHOT:
                if ec > el-1:
                    self.pwm.duty_u16(0)
                    #done=1
                else:
                    ec += 1
                    
            elif effectmode == PWM_RAMP:
                if ec > el-1:
                    # just stick with the last sample
                    done=1
                else:
                    ec += 1
                    
            elif effectmode == PWM_RAMPDOWN:
                if ec == 0:
                    # just stick with the last sample
                    done=1
                else:
                    ec -= 1
                    
            elif effectmode == PWM_CYCLIC:
                if ec >= el-1:
                    # Start from the beginning
                    ec=0
                else:
                    ec += 1
                    
            elif effectmode == PWM_BACKANDFORTH:
                
                if self.datadir: # 0 forward, 1 backward
                    # Backward
                    if ec <= 0:
                        self.update_datadir(0)
                        ec = 1
                    else:
                        ec -= 1
                        
                else:
                    # Forward
                    if ec >= el-1:
                        self.update_datadir(1)
                        ec -= 1
                    else:
                        ec += 1
                        
            self.update_effectcounter(ec)

            if done:
                print("done")
                self.timer.deinit()

if __name__ == '__main__':
    # Use onboard LED
    led=Pin(25, Pin.OUT)
    p = PWMEffect(led,pwm_freq=4000,update_ms=100) 
    effect=bytearray(8)
    effect[0]=0
    effect[1]=4
    effect[2]=8
    effect[3]=16
    effect[4]=32
    effect[5]=64
    effect[6]=128
    effect[7]=255

    p.play_effect(effect, 8, mode=PWM_RAMP)

    utime.sleep(2)
    p.stop_effect(rampdown=True)
                
