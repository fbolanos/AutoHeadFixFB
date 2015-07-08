__author__ = 'Federico'


from Modules import *
import RPi.GPIO as GPIO

class Task:
    def __init__(self):
        # Array that will hold all the Mice as Mouse objects.
        self.mice = []
        # Mouse object that holds the mouse currently inside.
        self.currentMouse = Mouse("0123456789")

        # output pin for the pistons
        self.pistons_pin = 24
        # output pin for the water dispenser
        self.reward_pin = 17
        # input pin for the tag in range on  the RFID reader
        self.range_pin = 18
        # input pin for the head bar contact in the chamber
        self.contact_pin = 22
        # output pin for the Blue LED.
        self.led_pin = 4
        # output pin for the stimulus LED
        self.stimulus_led_pin = 21

        # variables -timing
        # reward time, in seconds
        self.reward_time = 100e-3
        # time for mouse to get head off the contacts when session ends, so he won't be immediately fixed again
        self.skedaddle_time = 3
        # number of rewards to give in a head fix trial
        self.number_of_headfix_rewards = 6
        # time between rewards, in seconds
        # time of a session is (nRewards) * interRewardInterval
        self.inter_reward_interval = 5.0
        # maximum number of entrance rewards that will be given.
        self.maximum_entrance_rewards = 100
        # time before an entrance reward is given to avoid immediate in an outs
        self.entrance_reward_delay_time = 2.0
        # time for when the program is idling or waiting for something, ensures there isn't cpu overload.
        self.cpu_rest_time = 0.01
        # time the stimulus led remains on
        self.stimulus_led_on_time = 0.01 # 10ms

        # sets up the GPIO headers each for their respective functionality.
        self.setup_gpio_lines()

        # where to put the text file and video files
        self.data_file_path = "/media/118D-D10B/HeadFix2Data/TextFiles/"
        self.data_file_name = "headFix_"
        self.stats_file_name = "/media/118D-D10B/HeadFix2Data/TextFiles/currentStats_"
        self.video_path = "/media/118D-D10B/HeadFix2Data/movies/"
        #serial port, "/dev/ttyAMA0" for built-in serial port
        #  "/dev/ttyUSB0" for USB-to-Serial
        self.serial_port = "/dev/ttyAMA0"
        # Call the function that sets up what the files will be called.
        self.setup_full_path_data()

        # set up all the Modules
        # The RFID reader class
        self.reader = TagReader(self.serial_port)

        # The Camera class
        self.camera = BrainCamera()

        # The data collector/writer
        self.collector = DataCollector(self.data_file_path)



    def start(self):
        self.collector.save_start_session()

        # Main Loop of the proram.
        while True:
            print ("Waiting for a mouse...")
            # Loop for the reader, only exits when mouse is found.
            tag = self.tag_reader_loop()
            # At this point we know there is a tag inside
            # Now we will setup the mouse with this tag.
            self.setup_mouse(tag)

            # Runs the trial
            self.run_trial()

            # Saves to the current stats file.
            self.save_current_stats()

    def tag_reader_loop(self):
        while(self.reader.getBufferSize() < 16):
            sleep(self.cpu_rest_time)
        tag = self.reader.readTag()
        return tag

    def run_trial(self):
        self.collector.save_mouse_entry(self.currentMouse.tag)
        self.currentMouse.entries += 1

        # Delays the entrance reward for some time.
        t_start_trial = time()
        while(time()-t_start_trial < self.entrance_reward_delay_time):
            # If we manage to get mouse contact get out of here immediately!
            if GPIO.input(self.contact_pin):
                break
            # Mouse left the chamber before the 2 seconds!
            elif GPIO.input(self.range_pin) == 0:
                self.collector.save_mouse_exit(self.currentMouse.tag)
                return
            else:
                sleep(self.cpu_rest_time)

        # Mouse does not have contact, give him his entrance reward.
        if not GPIO.input(self.contact_pin):
            # Check if they are still allowed rewards.
            if (self.currentMouse.entrance_rewards < self.maximum_entrance_rewards):
                self.dispense_reward()
                self.currentMouse.entrance_rewards += 1


        # At this point we just wait for head fixation.
        while True:
            # Mouse made contact!
            if GPIO.input(self.contact_pin):
                self.headfix_loop()
            # Mouse left the chamber!
            elif GPIO.input(self.range_pin) == 0:
                self.collector.save_mouse_exit(self.currentMouse.tag)
                return
            else:
                sleep(self.cpu_rest_time)

    # Loop which runs once a mouse has had head contact
    def headfix_loop(self):
        # Fire the pistons
        GPIO.output(self.pistons_pin, True)
        self.currentMouse.headfixes += 1

        #Record fixation time
        fixation_time = time()
        self.collector.save_mouse_Headfix_start(self.currentMouse.tag, fixation_time)
        # Create the path for the video
        video_name = self.video_path + "M" + str(self.currentMouse.tag) + "_" + str(fixation_time) + ".raw"

        self.camera.start_recording(video_name)

        # Turn on the blue led
        GPIO.output(self.led_pin, True)

        for i in range(self.number_of_headfix_rewards):
            self.dispense_reward()
            self.collector.save_mouse_Reward_given(self.currentMouse.tag, i)
            self.currentMouse.headfixed_rewards += 1

            # Light stimulus occurs every 5 seconds!
            sleep(self.inter_reward_interval/2.0)
            #self.light_stimulus()
            sleep(self.inter_reward_interval/2.0)

            ## MODIFY HERE FOR INCLUDING OTHER STIMULI.
        # end of reward/stimuli loop

        # turn off the blue led
        GPIO.output(self.led_pin, False)

        self.camera.stop_recording()

        # turn off pistons
        GPIO.output(self.pistons_pin, False)

        # save end of headfixing
        self.collector.save_mouse_Headfix_end(self.currentMouse.tag)


        # Time before the mouse is headfixed again.
        sleep(self.skedaddle_time)

    # Simple light stimulus! 
    def light_stimulus(self):
        self.collector.save_light_stimulus(self.currentMouse.tag)
        GPIO.output(self.stimulus_led_pin, True)
        sleep(self.stimulus_led_on_time)
        GPIO.output(self.stimulus_led_pin, False)

    # Simply dispenses water reward.
    def dispense_reward(self):
        GPIO.output(self.reward_pin, 1)
        sleep(self.reward_time)
        GPIO.output(self.reward_pin, 0)

    # Naming scheme: headFix_XX_MMDD.txt
    def setup_full_path_data(self):
        cage_id = input("Type the cage ID: ")

        # This section of the code creates the appropriate name of the file.
        date_now = ""
        if datetime.now().month < 10:
            date_now += "0"
        date_now += str(datetime.now().month)

        if datetime.now().day < 10:
            date_now += "0"
        date_now += str(datetime.now().day)

        self.data_file_path += (self.data_file_name + cage_id + "_" + date_now + ".txt")
        self.video_path += cage_id + "/"
        self.stats_file_name += cage_id + ".txt"

        print ("The path of data file will be: " + self.data_file_path)
        print ("The path of the video files will be: " + self.video_path)
        print ("The path of the stats file will be: " + self.stats_file_name)

        ans = input("Is this correct? (y/n): ")

        if ans == "y":
            return
        else:
            self.setup_full_path_data()

    def setup_mouse(self, tag):
        # This function iterates through the list of mice and if it finds one
        # with the same tag it sets it as the curent Mouse, otherwise, it adds it
        # to the list as a new mouse.
        for mouse in self.mice:
            if mouse.tag == tag:
                self.currentMouse = mouse
                return
        print ("Mouse not found! Adding to the list!")
        # At this point we couldn't find the mouse in the list, so we
        #   create a new mouse object and append it to the list

        self.currentMouse = Mouse(tag)
        self.mice.append(self.currentMouse)

    def setup_gpio_lines(self):
        # set up GPIO use BCM mode for GPIO pin numbering
        GPIO.setmode (GPIO.BCM)
        GPIO.setup (self.pistons_pin, GPIO.OUT)
        GPIO.setup (self.reward_pin, GPIO.OUT)
        GPIO.setup (self.led_pin, GPIO.OUT)
        GPIO.setup (self.stimulus_led_pin, GPIO.OUT)
        GPIO.setup (self.range_pin, GPIO.IN)
        GPIO.setup (self.contact_pin, GPIO.IN)


    def save_current_stats(self):
        with open(self.stats_file_name, "w") as file:
            first_line = "Mouse_ID\tentries\tent_rew\thfixes\thf_rew\n"
            file.write(first_line)
            for mouse in self.mice:
                output_line = str(mouse.tag) + "\t" + str(mouse.entries) + "\t" + str(mouse.entrance_rewards) + "\t" + str(mouse.headfixes) + "\t" + str(mouse.headfixed_rewards) + "\n"
                file.write(output_line)

    def quit(self):
        self.collector.save_end_session()


def main():
    try:
        task = Task()
        task.start()
    except KeyboardInterrupt:
        task.quit()
        GPIO.cleanup()



main()