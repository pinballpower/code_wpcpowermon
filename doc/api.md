# API documentation

The API is quite simple. The main monitoring process just runs on Core 0 and updates all data in background. That means you can use the full Core 0 for your code and you don't have to care about resources for the poller.

## Basic use

```
from powermon_viper import PowerMonitor

pm=PowerMonitor()
pm.start()

while True:
  do_something()
  lamps = pm.get_lamps()
  solenoids = pm.get_solenoids()
  gi = pm.get_gi()
  stats = pm.get_stats() # Purely for your information
```

### get_lamps()
Returns the current state of the lamp matrix as an 64bit integer. To check the state of a specific lamp, use the bitwise AND operator

### get_solenoids()
Returns the current state of the lamp matrix as an 32bit integer. To check the state of a specific solenoid, use the bitwise AND operator

### get_gi()
Returns the brightness of the 3 or 5 GI channels as a 40bit integer. To get the state of a single channel use the bitwise AND operator and SHIFT bits

## Notifiers

While the previous methods allow you to poll the state of the system, there are also ways to get notified if a lamp or solenoid changes

```
def lamp_notify():
  global lamp_changed
  lamp_changed = True 
  
 
pm.set_lamp_notify(lamp_notify)
```

There is one important thing here: This function will run in the context of the power monitor thread. This means if this function blocks the CPU 
for a longer period (>1ms), you might loose data in the poller process. Don't use these functions for any major calculations, but just to notify your main
program that new data is available. 

### set_lamp_notify(lamp_notify)

Sets a lamp notify function that will be called if any lamp in the lamp matrix changes

### set_solenoid_notify(lamp_notify)

Sets a solenoid notify function that will be called if any solenoid changes

## Low level data access

You can directly import and acces the lamps, solenoids and gi_brightness data. These are bytearray which makes it even compatible with the Viper optimizer 
without additional type conversation. They are defined as follows:

```
lamps = bytearray(8)
solenoids = bytearray(4)
TRIAC_NUM = const(5)
gi_brightness = bytearray(TRIAC_NUM)
```

Using them in your own code is simple:

```
from powermon_viper import PowerMonitor, lamps, solenoids,gi_brightness

pm=PowerMonitor()
pm.start()

while True:
  do_something(lamps)
  do_something(solenoids)
  do_something(gi_brightness)
```


## Overclocking

If necessary (it's not needed for the poller) you can overclock the Pi up to 250MHz:
```
import machine

machine.freq()          # get the current frequency of the CPU
machine.freq(250000000) # set the CPU frequency to 250 MHz
```

This seems to run stable, but I recommend to do this only if your effects require the additional processing power


