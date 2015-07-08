__author__ = 'Federico'

from Modules import *


def test_TagReader():
    reader = TagReader(port)
    while (True):
        buffer_size = reader.getBufferSize()
        if (buffer_size == 16):
            # Read reader if and only if the buffer size is equal to 16.
            # Reason is that the data of the tag is exactly 16 bytes.
            print reader.readTag()
        else:
            sleep(0.01)



def test_Mouse():
    mouse = Mouse(12345678)

    mouse.entrance_rewards += 1
    print "Entrance_rewards should be = 1."
    print "Entrance rewards is actually: " + str(mouse.entrance_rewards)


def test_BrainCamera():
    camera = BrainCamera()
    camera.start_recording("~/Documents/test.h264")
    sleep(4)
    camera.stop_recording()

    print "Check the video and make sure it's 4 seconds long."


def test_DataCollector():
    tag = "0123456789"
    dataCollector = DataCollector("test.txt")
    dataCollector.save_start_session()
    dataCollector.save_mouse_entry(tag)
    dataCollector.save_mouse_Headfix_start(tag, time())
    for i in range(5):
        dataCollector.save_mouse_Reward_given(tag, i)
    dataCollector.save_mouse_Headfix_end(tag)
    dataCollector.save_mouse_exit(tag)
    dataCollector.save_end_session()

#test_TagReader()
#test_Mouse()
#test_BrainCamera()
test_DataCollector()