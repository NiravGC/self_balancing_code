########## MILESTONE 3 ##########
#   Process music in real time  #
#   Sync dance moves to music   #
# ----------------------------- #

import pyb
import time
from pyb import Pin, Timer, ADC, DAC, LED
from array import array					# need this for memory allocation to buffers
from oled_938 import OLED_938			# Use OLED display driver
from moves import *

import micropython
micropython.alloc_emergency_exception_buf(100)	# memory buffer for interrupts

print('MILESTONE 3')

# ----- OLED CONFIG ----- #
oled = OLED_938(pinout={'sda': 'Y10', 'scl': 'Y9', 'res': 'Y8'}, height=64, external_vcc=False, i2c_devid=61)
oled.poweron()
oled.init_display()

# ----- WHEEL ASSIGNMENT ----- #
A1 = Pin('X3', Pin.OUT_PP)		    # Control direction of motor A
A2 = Pin('X4', Pin.OUT_PP)
PWMA = Pin('X1')				    # Control speed of motor A
B2 = Pin('X7', Pin.OUT_PP)		    # Control direction of motor B
B1 = Pin('X8', Pin.OUT_PP)
PWMB = Pin('X2')				    # Control speed of motor B

# ----- TIMER ASSIGNMENT ----- #
tim = Timer(2, freq = 1000)
motorA = tim.channel (1, Timer.PWM, pin = PWMA)
motorB = tim.channel (2, Timer.PWM, pin = PWMB)

# -- MICROPHONE CONFIG -- #
mic = ADC(Pin('Y11'))
MIC_OFFSET = 1523		    # ADC reading of microphone for silence
dac = pyb.DAC(1, bits=12)  	# Output voltage on X5 (BNC) for debugging
b_LED = LED(4)			    # flash for beats on blue LED

N = 160					    # size of sample buffer s_buf[]
s_buf = array('H', 0 for i in range(N)) # reserve buffer memory
ptr = 0					    # sample buffer index pointer
buffer_full = False			# semaphore - ISR communicate with main program

def flash():				# routine to flash blue LED when beat detected
	b_LED.on()
	pyb.delay(20)
	b_LED.off()
	
def energy(buf):			    # Compute energy of signal in buffer
	sum = 0
	for i in range(len(buf)):
		s = buf[i] - MIC_OFFSET	# adjust sample to remove dc offset
		sum = sum + s*s		    # accumulate sum of energy
	return sum
# ------------------------- interrupt section ------------------------- #

# ----- ISR FOR SAMPLING DATA ----- #
def isr_sampling(null): 		    # timer interrupt at 8kHz
	global ptr, buffer_full		    # global variables
	
	s_buf[ptr] = mic.read()		    # take a sample every timer interrupt
	ptr += 1			            # increment buffer pointer (index)
	if (ptr == N):			        # wraparound ptr - goes 0 to N-1
		ptr = 0
		buffer_full = True	        # set the flag (semaphore) for buffer full

# ----- 125 MICROSEC INTERRUPT ----- #
pyb.disable_irq()			            # disable interrupt while configuring timer
sample_timer = pyb.Timer(7, freq=8000)	# set timer 7 for 8kHz
sample_timer.callback(isr_sampling)	    # specify interrupt service routine
pyb.enable_irq()			            # enable interrupt again

# ------------------------- end of interrupt section ------------------------- #

# ----- MAIN LOOP CONSTANTS ----- #
M = 50					        # number of instantaneous energy epochs to sum
BEAT_THRESHOLD = 2.0			# threshold for c to indicate a beat
SILENCE_THRESHOLD = 1.3			# threshold for c to indicate silence
SPEED = 60				        # baseline speed
POS = 0                     	# position in movelist (counter)
MOVELIST = []				    # empty list of moves to be added to
MOVE = 'w'				        # current move: to be updated
MOVEFUNC = {				    # corresponding function to move list value
	'F': danceforward,
	'FS': danceforwardslow,
	'B': danceback,
	'R': danceright,
	'RS': dancerightslow,
	'L': danceleft,
	'LS': danceleftslow
}

# ----- IMPORT MOVES ----- #
with open('movelist.txt') as file:	# select movelist text file
	for line in file:		# move through list line by line
		line = line.strip()	# remove formatting (i.e. \n)
		MOVELIST.append(line)	# add move to movelist
print(MOVELIST)

# initialise variables for main program loop 
e_ptr = 0					                # pointer to energy buffer
e_buf = array('L', 0 for j in range(M))     # reserve storage for energy buffer
sum_energy = 0					            # total energy in last 50 epochs
pyb.delay(100)
tic = pyb.millis()				            # mark time now in msec

# ----- IDLE BEFORE RUNNING ----- #
oled.draw_text(5, 20, 'MILESTONE 3: Ready')
oled.draw_text(5, 40, 'Press USR button')
oled.display()
print('Milestone 3: Ready')
print('Waiting for button press')

trigger = pyb.Switch()
while not trigger():
	time.sleep(0.001)
while trigger(): pass
print('Button pressed - running')
oled.clear()
oled.draw_text(5, 20, 'MILESTONE 3: Ready')
oled.draw_text(5, 40, 'Running Routine')
oled.display()

# ----- MAIN PROGRAM LOOP ----- #
try:
	while True:
		if buffer_full:		# semaphore signal from ISR - set if buffer is full
		
			# Calculate instantaneous energy
			E = energy(s_buf)
		
			# compute moving sum of last 50 energy epochs
			sum_energy = sum_energy - e_buf[e_ptr] + E
			e_buf[e_ptr] = E		    # over-write earlest energy with most recent
			e_ptr = (e_ptr + 1) % M		# increment e_ptr with wraparound - 0 to M-1
		
			# Compute ratio of instantaneous energy/average energy
			c = E*M/sum_energy
			dac.write(min(int(c*4095/3), 4095)) 	# useful to see on scope, can remove
		
			if (pyb.millis()-tic > 400):		    # if more than 400ms since last beat -
				if (c>BEAT_THRESHOLD):		        # look for a beat
					flash()				        # beat found, flash blue LED
					MOVE = MOVELIST[POS]		# take current move in file
					if MOVE != 'w':			# 'w' is a 'wait' -> no function
						M = MOVEFUNC[MOVE]	# find associated move function
                        M()                 # executes associated move function
					POS += 1			    # next move
					tic = pyb.millis()		# reset tic
			buffer_full = False				# reset status flag
finally:
    A1.low()
    A2.low()
    B1.low()
    B2.low()
    print('Finished')
