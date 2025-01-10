import os
import cv2
import json
import pickle
import numpy as np
import face_recognition
from datetime import datetime


# ================================================================================
# Loading all the required paths and files:
# ================================================================================

DEBUG = False
JSON_FOLDER = 'Jsons'
MODEL_FOLDER = 'Models'

attendance_log_file = os.path.join('Jsons', 'attendance_log.json')
class_register_file = os.path.join('Jsons', 'class.json')

# ================================================================================
# Globals to access from anywhere:
# ================================================================================

# Create global register dictionary to store all the student details:
register = {}

known_face_encodings = []
known_face_reg_no = []


# ================================================================================
# Timer class to calculate time taken by any of the threads/processes etc.:
# ================================================================================


class Timer:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.time_diff = None

    def start(self):
        self.start_time = datetime.now()

    def end(self):
        self.end_time = datetime.now()
        self.time_diff = (self.end_time - self.start_time).total_seconds()

    def get_diff(self):
        return self.time_diff

    def get_json(self, start_name='start_time', end_name='end_time', diff_name='time_diff'):
        return {
            start_name: self.start_time.strftime("%d/%m/%Y, %I:%M:%S %p"),
            end_name: self.end_time.strftime("%d/%m/%Y, %I:%M:%S %p"),
            diff_name: self.time_diff
        }

    def help(self):
        _help = """
            To use this Timer class, do the following:
            1. Create an object of Timer class
                t = Timer()
            2. Start the timer:
                t.start()
            3. End the timer:
                t.end()
            4. Get the time difference:
                t.get_time_diff()
            5. Get the time records in json format:
                t.get_json()
            6. To save json:
                with open("time.json", "w") as f:
                json.dump(t.get_json(), f, indent=4)
            *** That's it! ***
        """
        print(_help)
        return _help


# ================================================================================
# load the `class` json created from face modelling code (like a student register)
# ================================================================================


def load_register():
    with open(class_register_file, 'r') as file:
        tmp = json.load(file)

    # modify it to have all required things of actual register
    for stud in tmp:
        register[stud['Reg_No']] = {
            'Name': stud['Name'],
            'Reg_No': stud['Reg_No'],
            "Image": stud['Image'],
            "Pickle": stud['Pickle']
        }

    if DEBUG:
        print("\nRegister loaded from class.json:")
        print(json.dumps(register, indent=4), end='\n\n')


def load_known_faces():
    for stud in register.keys():
        file_name = register[stud]['Pickle']
        file_path = os.path.join(MODEL_FOLDER, file_name)

        with open(file_path, 'rb') as file:
            known_face_encodings.append(pickle.load(file))

        known_face_reg_no.append(register[stud]['Reg_No'])

        if DEBUG:
            reg_no = register[stud]['Reg_No']
            name = register[stud]['Name']
            print(f"Loaded Model -> ({reg_no}) {name}")


# ================================================================================
# Actual code which checks the attendance, given a frame/image:
# ================================================================================

def check_attendance(frame: str) -> list:
    """
    Function which takes just one image_path and returns the reg_no of present people

    Args:
        frame (str | list): path of the file

    Returns:
        list: list with reg no of present people
    """

    video_capture = cv2.VideoCapture(frame)
    # video_capture = cv2.imread(frame)

    # Frame pre-processing:
    _, frame = video_capture.read()
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = np.ascontiguousarray(small_frame[:, :, ::-1])

    # get the locations where faces are recognized:
    face_locations = face_recognition.face_locations(rgb_small_frame)

    # get the encodings of those recognized faces:
    face_encodings = face_recognition.face_encodings(
        face_image=rgb_small_frame,
        known_face_locations=face_locations,
        num_jitters=1
    )

    # ------------------------------------------------------------------------
    present_people = []

    # for all the faces found in this image/frame:
    for face_encoding in face_encodings:

        # get a list of true/false for match-found with all the known encodings:
        matches = face_recognition.compare_faces(
            known_face_encodings=known_face_encodings,
            face_encoding_to_check=face_encoding
        )

        # this returns list of distances with all the known encodings
        face_distance = face_recognition.face_distance(
            face_encodings=known_face_encodings,
            face_to_compare=face_encoding
        )

        # find the person with minimum dist (best match):
        best_match_index = np.argmin(face_distance)
        # later this will be also cross checked with matches list [True/False]
        # Then declared as present or not finally

        # if that minimum dist image exists in matches as True, then mark present:
        if matches[best_match_index] == True:
            reg_no = known_face_reg_no[best_match_index]
            present_people.append(reg_no)

    video_capture.release()
    cv2.destroyAllWindows()
    return present_people


# ================================================================================
# Logging helper functions to save logs:
# ================================================================================

def create_log(log: dict):
    """Creates a log and appends it to the file"""
    # Create a new file if it doesn't exist:
    if not os.path.exists(attendance_log_file):
        with open(attendance_log_file, 'w') as file:
            json.dump([], file)

    # Load the existing data:
    with open(attendance_log_file, 'r') as file:
        data = json.load(file)

    # Append the new log:
    data.append(log)
    with open(attendance_log_file, 'w') as file:
        json.dump(data, file, indent=4)


# ================================================================================
# Main function which will be called from the other file:
# ================================================================================

def check_image(image_data: str, timestamp: str) -> dict:
    """
    Processes a single image for attendance checking.

    Args:
        image_data: The image (path) to be checked.
        timestamp: The timestamp associated with the image.

    Returns:
        dict: Log data including timestamp, processing times, and list of people present.
    """
    # Timer for attendance checking
    timer = Timer()
    timer.start()
    present = check_attendance(image_data)
    timer.end()

    # Get time records for image processing:
    time_records = timer.get_json(
        start_name="task_start_time",
        end_name="task_end_time",
        diff_name="task_time_taken"
    )

    response = {
        "timestamp": timestamp,
        "time_records": time_records,
        "people_present": present,
    }

    create_log(response)
    return response


def init():
    load_register()
    load_known_faces()


# ================================================================================
# Testing:
# ================================================================================

if __name__ == "__main__":
    DEBUG = True
    init()
    image_path = 'temp_test.jpg'
    timestamp = '9/1/2025, 11:06:12 pm, 0'
    print(f"\nChecking attendance for image: `{image_path}` @ [{timestamp}]")
    response = check_image(image_path, timestamp)
    print(json.dumps(response, indent=4))
