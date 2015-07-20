__author__ = 'Federico'

from serial import Serial
import picamera
from time import sleep, time
from datetime import datetime
import RPi.GPIO as GPIO

port = "/dev/ttyUSB0"

class TagReader:
    def __init__(self, port):
        self.serial_port = Serial(port, baudrate=9600, timeout=0.01)
        self.serial_port.close()
        self.serial_port.open()
        self.serial_port.flush()  # Flush any old data
        self.should_do_checksum = True

    def getBufferSize(self):
        return self.serial_port.inWaiting()

    """
    RFID Tag is 16 characters: STX(02h) DATA (10 ASCII) CHECK SUM (2 ASCII) CR LF ETX(03h)
    1 char of junk, 10 of hexadecimal data, 2 of hexadecimal check sum, 3 of junk
    XOR-ing 5 1-byte hex values will give the 1-byte check sum - if requested
    """
    def readTag(self):
        #  run the while loop since it may read a tag twice.
        #  May not be necessary
        while (self.getBufferSize() >= 16):
            junk = self.serial_port.read(1)  # Junk byte 1
            tag  = self.serial_port.read(10) # tag bytes 10
            check_sum = self.serial_port.read(2) # check sum 2 bytes
            junk = self.serial_port.read(3)  # Last 3 bytes are junk

            if (self.should_do_checksum):
                self.doCheckSum(tag, check_sum)

        return int(tag, base=16)  # Convert the tag to an integer.

    def doCheckSum(self, tag, check_sum):
        try:
            checked_val = 0
            for i in range(0,5):
                checked_val = checked_val ^ int(tag [(2 * i) : (2 * (i + 1))], 16)

            if checked_val != int(check_sum, 16):
                print ("Tag reader checksum error. Tag was not read fully...")
        except ValueError:
            print ("Error reading the tag properly.")
            print ("Tag: " + tag)

    def close(self):
        self.serial_port.close()


class Mouse:
    def __init__(self, tag):
        self.tag = tag
        self.entries = 0
        self.headfixes = 0
        self.entrance_rewards = 0
        self.headfixed_rewards = 0


class BrainCamera:
    def __init__(self):
        self.video_format = "rgb"
        #self.video_quality = 5

        # Set up the settings of the camera so that
        # Exposure and gains are constant.
        self.camera = picamera.PiCamera()
        self.camera.resolution = (256,256)
        self.camera.framerate = 30
        sleep(2.0)
        self.camera.shutter_speed = self.camera.exposure_speed
        self.camera.exposure_mode = 'off'
        g = self.camera.awb_gains
        self.camera.awb_mode = 'off'
        self.camera.awb_gains = g
        self.camera.shutter_speed = 30000
        self.camera.awb_gains = (1,1)

    def start_recording(self, video_name_path):
        self.camera.start_recording(video_name_path, format=self.video_format)
        self.camera.start_preview()

    def stop_recording(self):
        self.camera.stop_recording()
        self.camera.stop_preview()

    # Destructor
    def __del__(self):
        print ("Closed Camera")
        self.camera.close()


class DataCollector:
    """
    Format of the output string:
    tag     time_epoch      datetime       event
    """
    def __init__(self, data_file_path):
        self.data_file_path = data_file_path

    # This functions saves and prints the output string
    # Tag is the tag of the mouse inside
    # time_event is when did the event happen
    # event is the type of event occurring (i.e. entry, exit, reward, etc)
    def save_helper(self, tag, time_event, event):
        with open(self.data_file_path, 'a') as data_file:
            output_string = str(tag) + '\t' + str(time_event) + '\t' + str(datetime.now()) + '\t' + event + '\n'
            print (output_string)
            data_file.write(output_string)

    def save_start_session(self):
        self.save_helper('0000000000', time(), 'SeshStart')

    def save_mouse_entry(self, tag):
        self.save_helper(tag, time(), 'entry')

    def save_mouse_Headfix_start(self, tag, time_headfix):
        self.save_helper(tag, time_headfix, 'check+')

    def save_mouse_Reward_given(self, tag, n_reward):
        self.save_helper(tag, time(), 'reward' + str(n_reward))

    ''' led_side is one of:
            L for left LED
            C for center LED
            R for right LED
    '''
    def save_light_stimulus(self, tag, led_side):
        self.save_helper(tag, time(), 'light-' + led_side)

    def save_simple_stimulus(self, tag, counter):
        self.save_helper(tag, time(), 'stimulus-' + str(counter))

    def save_mouse_Headfix_end(self, tag):
        self.save_helper(tag, time(), 'complete')

    def save_mouse_exit(self, tag):
        self.save_helper(tag, time(), 'exit')

    def save_end_session(self):
        self.save_helper('0000000000', time(), 'SeshEnd')


class LightStimulus():
    def __init__(self, left, center, right, time_on, length, frequency):
        # output pin for the stimulus the left LED (blue cable)
        self.stimulus_left_led_pin = left
        # output pin for the stimulus the center led (green cable)
        self.stimulus_center_led_pin = center
        # output pin for the stimulus the right led (red cable)
        self.stimulus_right_led_pin = right
        # time to turn on the LED
        self.stimulus_led_on_time = time_on
        # length of stimulation train in seconds
        self.length_of_light_stimulus_train = length
        # frequency of light stimulation in Hz
        self.light_stimulation_frequency = frequency
        # Total number of flashes.
        self.number_of_led_flashes = int(self.light_stimulation_frequency * self.length_of_light_stimulus_train)
        # Calculate the off period of the LED per flash
        self.stimulus_led_off_time = (1.0/self.light_stimulation_frequency) - self.stimulus_led_on_time
        self.setup_gpio_for_leds()

        # Constant for the light stimulus contains L, C, R
        self.led_to_turn_on = ['L', 'R', 'L']
        self.counter = 0
        self.number_of_leds = len(self.led_to_turn_on)

    def setup_gpio_for_leds(self):
        GPIO.setup (self.stimulus_left_led_pin, GPIO.OUT)
        GPIO.setup (self.stimulus_center_led_pin, GPIO.OUT)
        GPIO.setup (self.stimulus_right_led_pin, GPIO.OUT)

    # Simple light stimulus!
    def stimulate(self, collector, tag):
        collector.save_light_stimulus(tag, self.led_to_turn_on[self.counter])

        # Left LED's turn
        if self.led_to_turn_on[self.counter] == 'L':
            led_pin_to_use = self.stimulus_left_led_pin
        # Right LED's turn
        elif self.led_to_turn_on[self.counter] == 'R':
            led_pin_to_use = self.stimulus_right_led_pin
        else: # Center's LED
            led_pin_to_use = self.stimulus_center_led_pin

        self.counter = (self.counter + 1) % self.number_of_leds

        # Iterate through all the number of flashes.
        for i in range(self.number_of_led_flashes):
            GPIO.output(led_pin_to_use, True)
            sleep(self.stimulus_led_on_time)
            GPIO.output(led_pin_to_use, False)
            sleep(self.stimulus_led_off_time)


class SimpleStimulus():
    def __init__(self, trigger_pin, duration):
        # output pin that will go high
        self.trigger_pin = trigger_pin
        # duration of the high output in seconds
        self.duration = duration

        self.setup_gpio_lines()

    def setup_gpio_lines(self):
        GPIO.setup(self.trigger_pin, GPIO.OUT)

    def stimulate(self, collector, tag, counter):
        collector.save_simple_stimulus(tag, counter)

        #Turn on the trigger for 'duration' time
        GPIO.output(self.trigger_pin, True)
        sleep(self.duration)
        GPIO.output(self.trigger_pin, False)
