from machine import Pin, PWM, Timer
import utime

PWM_OFF = const(0)              # Output nothing
PWM_SINGLESHOT = const(1)       # Play the effect once and turn off
PWM_RAMP = const(2)             # Play the effect once and let the last effect sample running
PWM_CYCLIC = const(3)           # Cycle the effect
PWM_BACKANDFORTH = const(4)     # Cycle forward/backward through the effect

class PWMEffect():
    
    def __init__(self, pin_number, pwm_freq=1000, update_us=10000):
        self.pwm = PWM(Pin(pin_number))
        self.pwm.freq(pwm_freq)
        self.pwm.duty_u16(0)
        
        self.effectlen=0
        self.effect=bytearray(0)
        self.effectcounter=0
        self.effectdir=0
        self.update_us=update_us
        
    def play_effect(self, data, datalen, mode=PWM_OFF):
        self.effectcounter = 0
        self.effect=data
        self.effectlen=datalen
        self.effectmode=mode
        self.timer = Timer(period=self.update_us, mode=Timer.PERIODIC, callback=self.update_data())
            
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
                    
            elif effectmode == PWM_CYCLIC:
                if ec >= el-1:
                    # Start from the beginning
                    ec=0
                else:
                    ec += 1
                    
            elif effectmode == PWM_BACKANDFORTH:
            
                if self.datadir: # 0 forward, 1 backward

                    if ec >= el-1:
                        self.datadir = 1
                        ec -= 1
                    else:
                        ec += 1
                        
                else:
                        
                    if ec <= 0:
                        self.datadir = 0
                        ec = 1
                    else:
                        ec -= 1
                                 
            self.effectcounter = ec
            
            if done:
                self.timer.deinit()
                
p = PWMEffect(25,update_us=1000000) # Use onboard LED
effect=bytearray(2)
effect[0]=0
effect[1]=0xff
p.play_effect(effect, 2, mode=PWM_CYCLIC)

utime.sleep(4)
                