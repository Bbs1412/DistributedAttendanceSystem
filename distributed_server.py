import os
import time
import json
import socket
import threading
import logger as l
from typing import Literal
from datetime import datetime
from dotenv import load_dotenv
from networking import receive_message, send_message, handle_recv, handle_send


# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------


load_dotenv()

# Required files and folders:
CLASS_REGISTER = os.environ.get('class_register')
UPLOADS = os.environ.get('upload_folder')
MODELS = os.environ.get('face_models_folder')

UPLOADED_DATA = os.environ.get('uploaded_data')
ATTENDANCE_LOG_FILE = os.environ.get('attendance_raw_file')
ATTENDANCE_REGISTER = os.environ.get('class_attendance')

# Required server configurations:
HOST = str(os.environ.get('server_host'))
PORT = int(os.environ.get('server_port'))
TIMEOUT = int(os.environ.get('server_timeout'))
NO_OF_CLIENTS = int(os.environ.get('no_of_clients'))

# Global clients dictionary to access clients from anywhere:
clients = {}
# 'sample_client_3': {
#     'name': 'Sample Client',
#     'socket': "python_data",
#     'address': "192.168.13.12",
#     'is_free': True
# }

# Global server socket to access from anywhere:
server_socket = None

for i in range(NO_OF_CLIENTS):
    clients[str(i + 1)] = None

lock = threading.Lock()
responses = []

# Console logging modes:
INFO = '\033[94m[INFO]\033[0m'
WARN = '\033[93m[WARN]\033[0m'
ERROR = '\033[91m[ERROR]\033[0m'

# ------------------------------------------------------------------------------
# Utility functions:
# ------------------------------------------------------------------------------


def append_response(response):
    with lock:
        responses.append(response)
        with open(ATTENDANCE_LOG_FILE, 'w') as file:
            json.dump(responses, file, indent=4)


def get_timestamp():
    return datetime.now().strftime('%Y-%m-%d_%I-%M-%S_%p')


# ------------------------------------------------------------------------------
# Manage the connections with clients:
# ------------------------------------------------------------------------------

def start_server():
    global server_socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.settimeout(TIMEOUT)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)

    print(f"{INFO} Server started at `{HOST}:{PORT}`")
    l.create_log(
        topic='Server', status='Info', client_id=-1,
        message=f"Server started at `{HOST}:{PORT}` for timeout = {TIMEOUT} seconds.")

    return server_socket


def stop_server():
    global server_socket
    server_socket.close()
    print(f"{WARN} Server shut down.")
    l.create_log(topic='Server', status='Info', client_id=-1,
                 message="Server shut down.")


def get_clients():
    """Get all the clients connected to the server.
    Store them in the clients dictionary."""
    print(f"{INFO} Waiting for {NO_OF_CLIENTS} clients to connect...")

    client_sockets = []
    client_threads = []

    while len(client_sockets) < NO_OF_CLIENTS:
        client_socket, client_address = server_socket.accept()
        client_sockets.append(client_socket)

        client_init_thread = threading.Thread(
            target=handle_client_initialization,
            args=(client_socket, client_address, True),
            daemon=True
        )
        client_threads.append(client_init_thread)
        client_init_thread.start()

    # Wait for all client initialization threads to finish
    for client_init_thread in client_threads:
        client_init_thread.join()

    print(f"{INFO} All {NO_OF_CLIENTS} clients connected.")
    return True


def release_clients():
    """Release all the clients connected to the server."""
    for client_id, client in clients.items():
        if client is not None:
            client['socket'].close()
            clients[client_id] = None
    print(f"{WARN} All clients released.")
    l.create_log(topic='Connection', status='Info', client_id=-1,
                 message="All clients released.")


def handle_client_initialization(client_socket, client_address, slow=False):
    """Handle initial communication with a client."""
    global clients
    slow_mode = 1 if slow else 0

    try:
        client_id = 0
        client_name = 'Unresolved'

        # Dynamically assign the first available client_id:
        for i in range(NO_OF_CLIENTS):
            cid = str(i + 1)
            if clients[cid] == None:
                # Assign that client-id
                client_id = cid
                # Block that client-id temporarily (else concurrency issues might occur)
                clients[cid] = 'hold'
                break

        # print(f"{INFO} Client {client_id} : Connected Successfully {client_address}")

        # S1 - Send welcome message to client:
        handle_send(*send_message(client_socket, topic='Hi'),
                    log_topic='Connection - Welcome', log_client_id=client_id,
                    log_success_message='Client welcome message sent successfully.')
        time.sleep(slow_mode)

        # R1 - Receive client name from client:
        resp = handle_recv(
            *receive_message(client_socket), expected_topic='setup',
            log_client_id=client_id, log_topic='Connection - Device Name',
            log_success_message='Client setup message received successfully.')
        client_name = resp['message']

        # Update the shared state:
        clients[client_id] = {
            "name": client_name,
            "socket": client_socket,
            "address": client_address,
            "is_free": True     # For dynamic load balancing only
        }

        print(f"{INFO} Client {client_id} : Connected Successfully {client_address} - `{client_name}`")

        # S2 - Send client ID assigned to the client:
        handle_send(
            *send_message(client_socket, topic='Client Id', message=client_id),
            log_topic='Connection - Client Info',
            log_client_id=client_id, log_success_message=client_name)
        time.sleep(slow_mode)

        # S3 - Send class file to the client:
        handle_send(*send_message(
            client_socket, topic='Class Register', file_path=CLASS_REGISTER),
            log_client_id=client_id, log_topic='Initialization - Class Register',
            log_success_message='Class register sent successfully.')
        time.sleep(slow_mode)

        # S4 - Send the model count first to client:
        count = str(len(os.listdir(MODELS)))
        handle_send(
            *send_message(client_socket, topic='Models Count', message=count),
            log_topic='Initialization - Models Count', log_client_id=client_id,
            log_success_message='Model count sent successfully.')
        time.sleep(slow_mode)
        
        # S5 - Send all the the models to the client:
        for i, file in enumerate(os.listdir(MODELS)):
            file_path = os.path.join(MODELS, file)
            handle_send(
                *send_message(client_socket, topic='Pickle', file_path=file_path),
                log_topic='Initialization - Models', log_client_id=client_id,
                log_success_message=f'Model {i} sent successfully.')

        # Create a log for all the models sent successfully:
        l.create_log(
            topic='Initialization - Models', status='Success',
            client_id=client_id, message=f'Sent all the face models successfully.')

        # Mark end of initialization phase
        msg = f"{INFO} Client {client_id} : Initialization phase completed."
        print(msg)
        l.create_log(topic='Initialization - Complete', message=msg,
                     status='Success', client_id=client_id)

    except Exception as e:
        l.create_log(
            topic='Connection', status='Error', client_id=client_id,
            message=f'Client {client_id} - `{client_name}` connection error: {e}')
        print(f"[ERROR] Client {client_id} Initialization Error \n\t{e}")


# ------------------------------------------------------------------------------
# Static Load Balancing Functions:
# ------------------------------------------------------------------------------


def static_mode_thread(image_list, timestamp_list, client_id):
    """Threaded function to handle the static load balancing."""

    client_socket = clients[str(client_id)]['socket']
    client_name = clients[str(client_id)]['name']

    # S1 - Send the image count to the client:
    handle_send(*send_message(
        client_socket, topic='Static Images Count', message=len(image_list)),
        log_topic='Load Balancing', log_client_id=client_id,
        log_success_message='Image count sent successfully.')

    # Send the images and timestamps to get response:
    for i, (image, timestamp) in enumerate(zip(image_list, timestamp_list)):
        # S2 - Send the timestamp:
        handle_send(*send_message(
            client_socket, topic='Static Image',
            message=timestamp, file_path=image),
            log_topic='Load Balancing - Image', log_client_id=client_id,
            log_success_message=f'Image {i} - [{timestamp}] sent successfully.')

        print(f"{INFO} Client {client_id} : Image {(i+1):02d} - [{timestamp}] sent.")

        # R1 - Receive the processed data from the client:
        resp = handle_recv(
            *receive_message(client_socket), expected_topic='Processed Data',
            log_topic='Load Balancing - Processed Data', log_client_id=client_id,
            log_success_message=f'Image {i} - [{timestamp}] processed successfully.')

        # Save the response:
        processed_data = json.loads(resp['message'])
        append_response(processed_data)

    print(f"{INFO} Client {client_id} : All Image Processing completed.")


def static_mode(image_files, timestamps, frames_count):
    """Static load balancing strategy.

    Method:
    - Divide the images equally among the clients.
    - Run parallel threads for each client.
    - Each client processes the images in parallel (distributed processing).
    - Each client sends back the processed data to the server.
    """
    print(f"{INFO} Static mode selected. Starting static load balancing...")
    per_client = frames_count // NO_OF_CLIENTS
    print(f"{INFO} Dividing {frames_count} frames into {per_client} frames per client.")

    divided_data = [
        {
            "images": image_files[i * per_client: i * per_client + per_client],
            "timestamps": timestamps[i * per_client: i * per_client + per_client]
        } for i in range(NO_OF_CLIENTS)]

    # Code here for the part to split the images to process them in parallel
    threads = []
    for i in range(NO_OF_CLIENTS):
        client_id = i + 1
        thread = threading.Thread(
            target=static_mode_thread,
            args=(divided_data[i]['images'],
                  divided_data[i]['timestamps'],
                  client_id),
            daemon=True
        )
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    print(f"{INFO} Static load balancing completed.")


# ------------------------------------------------------------------------------
# Dynamic Load Balancing Functions:
# ------------------------------------------------------------------------------


def dynamic_mode_thread(image, timestamp, client_id):
    client_socket = clients[client_id]['socket']
    clients[client_id]['is_free'] = False  # Mark client as busy

    try:
        # Send the task to the client
        handle_send(*send_message(
            client_socket, topic='Dynamic Task', message=timestamp, file_path=image),
            log_topic='Load Balancing', log_client_id=client_id,
            log_success_message=f"Task [{timestamp}] sent successfully.")
        print(f"{INFO} Client {client_id} : Task [{timestamp}] sent.")

        # Wait for the client to process the task and respond
        resp = handle_recv(
            *receive_message(client_socket), expected_topic='Processed Data',
            log_topic='Load Balancing - Processed Data', log_client_id=client_id,
            log_success_message=f"Task [{timestamp}] processed successfully.")

        # Save the response
        processed_data = json.loads(resp['message'])
        append_response(processed_data)

    except Exception as e:
        print(f"[ERROR] Client {client_id} failed to process task: {e}")

    finally:
        clients[client_id]['is_free'] = True  # Mark client as free again


def dynamic_mode(image_files, timestamps, frames_count):
    """Dynamic load balancing strategy.

    Method:
    - All the images are stored in task_queue.
    - Send the images to the clients one by one.
    - The client which is free processes the image.
    - The client sends back the processed data to the server.
    """

    task_queue = list(zip(image_files, timestamps))
    total_tasks = len(task_queue)

    print(f"{INFO} Dynamic mode selected. Starting dynamic load balancing...")

    while len(task_queue) > 0:
        for client_id, client in clients.items():
            if client['is_free'] and len(task_queue) > 0:
                # Assign the next task to the free client
                image, timestamp = task_queue.pop(0)
                thread = threading.Thread(
                    target=dynamic_mode_thread,
                    args=(image, timestamp, client_id),
                    daemon=True
                )
                thread.start()

        # The thread in the end marks the client as free again
        # So we do not need the thread.join() here

        # Adding a small delay to avoid busy-waiting
        threading.Event().wait(0.1)

    # Wait for all (ongoing) threads to finish
    wait = True
    while wait:
        wait = False
        for client_id, client in clients.items():
            if not client['is_free']:
                wait = True
                print(f"{WARN} Client {client_id} is still processing a task. Waiting...")
                threading.Event().wait(1)

    # Send 'Done' message to all clients
    for client_id, client in clients.items():
        client_socket = client['socket']

        handle_send(*send_message(client_socket, topic='Dynamic Task', message="Done"),
                    log_topic='Load Balancing', log_client_id=client_id,
                    log_success_message='All tasks processed successfully.')

    print(f"{INFO} All tasks processed successfully.")


# ------------------------------------------------------------------------------
# Load Balancing Manager:
# ------------------------------------------------------------------------------

def start_load_balancing():
    """Start the load balancing strategy. To handle the attendance calculation."""
    print(f"{INFO} Starting the load balancing strategy...")

    # Read the uploaded_data json file:
    with open(UPLOADED_DATA, 'r') as f:
        data = json.load(f)

    image_files = data['files']
    timestamps = data['js_mod']
    frames_count = data['frame_count']
    processing_mode = data['processing_mode']

    # Log the mode of operation:
    l.create_log(client_id=-1, topic='Load Balancing - Mode',
                 message=processing_mode, status='Info')

    # Send: Inform clients the mode of operation:
    for i in range(NO_OF_CLIENTS):
        client_id = str(i + 1)
        client_socket = clients[client_id]['socket']

        handle_send(*send_message(
            client_socket, topic='Load Balancing', message=processing_mode),
            log_topic='Load Balancing - Mode', log_client_id=client_id,
            log_success_message='Load balancing mode sent successfully.')

    # Start the load balancing strategy
    if processing_mode.lower() == 'static':
        static_mode(image_files, timestamps, frames_count)

    elif processing_mode.lower() == 'dynamic':
        dynamic_mode(image_files, timestamps, frames_count)

    else:
        msg = f"[ERROR] Invalid processing mode: {processing_mode}."
        msg += "Please select either 'static' or 'dynamic'."
        l.create_log(topic='Load Balancing - Mode',
                     status='Error', client_id=-1, message=msg)
        raise ValueError(msg)


# ------------------------------------------------------------------------------
# (Post processing) Compile the results and save the attendance:
# ------------------------------------------------------------------------------


def get_datetime(js_mod_dt):
    """Returns the timestamp (in Python-datetime format) and the frame-number from the js_mod_dt string

    ip = "8/8/2024, 12:56:36 am, 0"
    op = datetime(2024, 8, 8, 0, 56, 36) and 0
    """
    number = js_mod_dt.split(",")[-1].strip()
    stamp = ', '.join(js_mod_dt.split(",")[:-1])
    dt_timestamp = datetime.strptime(stamp, "%d/%m/%Y, %I:%M:%S %p")
    return dt_timestamp, int(number)


def compare_timestamps(ts1: str, ts2: str,
                       comparison: Literal['earlier', 'later']) -> str:
    """Compare two timestamps and return the older/newer one."""

    # If any of the timestamps is not init, return the other one:
    if ts1 == -1:
        return ts2
    if ts2 == -1:
        return ts1

    dt1, frame1 = get_datetime(ts1)
    dt2, frame2 = get_datetime(ts2)

    if comparison == 'earlier':
        # if ts1 came earlier than ts2 (so far),
        #   or
        # (if the ts1 n ts2 are same [and] the frame1 is smaller than frame2)
        if (dt1 < dt2) or (dt1 == dt2 and frame1 < frame2):
            return ts1
        else:
            return ts2

    elif comparison == 'later':
        # if ts1 came later than ts2 (so far),
        #   or
        # (if the ts1 n ts2 are same [and] the frame1 is larger than frame2)
        if (dt1 > dt2) or (dt1 == dt2 and frame1 > frame2):
            return ts1
        else:
            return ts2


def update_register(register: dict, present: list, timestamp: str):
    """ Updates the register with the present people and their attendance status

    Args:
        present (list): List of registration numbers of present students.
        timestamp (str): Timestamp of the image.
    """
    for reg_no in register.keys():
        # If the student is not present, mark the attendance as False
        if reg_no not in present:
            register[reg_no]['Attendance'][timestamp] = False

        else:
            # If the student is present, mark the attendance as True
            # and update the first and last in timestamps

            register[reg_no]['Attendance'][timestamp] = True

            register[reg_no]['First_In'] = compare_timestamps(
                register[reg_no]['First_In'], timestamp, 'earlier')

            register[reg_no]['Last_In'] = compare_timestamps(
                register[reg_no]['Last_In'], timestamp, 'later')


def mark_attendance(register: dict, debug: bool = False):
    """Marks the attendance of each student in the register (75% criteria)"""

    if debug:
        print(f'\n[Attendance Info]: Marking attendance...')
        print(f'    | {"Reg".center(10)} | {"Name".center(15)} | {"Present".center(10)} | {"Absent".center(10)} | {"Percentage".center(10)} | {"Status".center(10)} |')

    for stud in register.values():
        present = 0
        absent = 0

        # iterate over all the time-stamps:
        for stamp in stud['Attendance'].keys():
            # print(stud['Attendance'][stamp])
            if (stud['Attendance'][stamp]):
                present += 1
            else:
                absent += 1

        if (present + absent) == 0:
            percentage = 0
        else:
            percentage = round((present / (present + absent)) * 100)
        stud['Percentage'] = percentage
        status = 'Present' if percentage >= 75 else 'Absent'
        stud['Status'] = status

        if debug:
            t_reg = str(stud['Reg_No']).center(10)
            t_name = str(stud['Name'][:15]).center(15)

            print(
                f'    | {t_reg} | {t_name} | {str(present).center(10)} | {str(absent).center(10)} | {str(percentage).center(10)} | {status.center(10)} |')
            # print(f'[Attendance Info]: Present: {present}, Absent: {absent}')
            # print(f'[Attendance Info]: Status: {status}, Percentage: {percentage}')


def save_register(register: dict):
    """Saves the register to the file"""
    with open(ATTENDANCE_REGISTER, "w") as f:
        json.dump(register, f, indent=4)


def compile_results(debug: bool = False):
    """Fn to compile individual responses of all the images and save the attendance."""

    # load the register from the file:
    with open(CLASS_REGISTER, 'r') as file:
        stud_info_list = json.load(file)

    register = {}
    for stud in stud_info_list:
        register[stud['Reg_No']] = {
            'Name': stud['Name'],
            'Reg_No': stud['Reg_No'],
            "Disp_name": stud['Disp_name'],
            # "Image": stud['Image'],
            # "Pickle": stud['Pickle'],

            "First_In": -1,
            "Last_In": -1,
            "Attendance": {},
            "Percentage": -1,
            "Status": -1,
        }

    # Load the responses from the file:
    with open(ATTENDANCE_LOG_FILE, 'r') as file:
        responses = json.load(file)

    # Compile the results from all the responses:
    for response in responses:
        present = response['people_present']
        timestamp = response['timestamp']
        update_register(register, present, timestamp)

    mark_attendance(register, debug=debug)
    save_register(register)


# ------------------------------------------------------------------------------
# Main driver part:
# ------------------------------------------------------------------------------


def driver_function():
    """Main driver function to start load balancing strategies.

    This (parallel) Server has already been started from the main flask server
    Also, get_clients() has already been called from the main flask server

    This driver function will be called when images and jsons are ready 
    This fn will handle all the communication and processing in clients
    And will return the attendance json to the main flask server
    """
    start_load_balancing()
    compile_results()
    release_clients()
    stop_server()


# ------------------------------------------------------------------------------
# Entry point: (Can run this file independently for testing)
# This name=main part is run only when this file is run as independent script.
# This part will not run when this file is imported in another file.
# The web-server will import required functions from this file.
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    # # compile_results(debug=True)

    start_server()
    get_clients()

    # Start the load balancing strategy (for testing):
    if input(f"{WARN} Press Enter to start the load balancing strategy...") != '':
        print(f"{WARN} Load balancing aborted. Exiting...")
        exit()

    driver_function()
