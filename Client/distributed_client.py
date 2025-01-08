# Client functions:
# Make folders: Models, Images, Results
# Connect to server first, send the device name to server
# Get all the pickles from server in response w/ device_id
# Get the images and names from the server
# Process based on the model and send the results back to the server

import os
import json
import time
import socket
import threading
from datetime import datetime
from networking import receive_message, send_message, handle_send, handle_recv

# ------------------------------------------------------------------------------
# Global vars :
# ------------------------------------------------------------------------------

# SERVER_IP = "192.168.83.125"
SERVER_IP = "localhost"
SERVER_PORT = 12345
DEVICE_NAME = socket.gethostname()

MODELS_FOLDER = './Models/'
IMAGES_FOLDER = './Images/'
JSONS_FOLDER = './Jsons/'

MY_CLIENT_ID = None
LOGS = []

file_save_lock = threading.Lock()

# ------------------------------------------------------------------------------
# Utility functions:
# ------------------------------------------------------------------------------


def prepare_folder(folder_path: str):
    """Prepare the folder by deleting all files in it. 
    Or create it if it doesn't exist."""
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            os.remove(os.path.join(folder_path, file))
    else:
        os.makedirs(folder_path, exist_ok=True)


def append_log(log: dict):
    LOGS.append(log)

    with file_save_lock:
        with open(os.path.join(JSONS_FOLDER, f'logs.json'), 'w') as f:
            json.dump(LOGS, f, indent=4)


def get_timestamp():
    return datetime.now().strftime('%Y-%m-%d_%I-%M-%S_%p')


def print_header(title=None, pre_lines=1, post_lines=1, header=True, footer=True):
    red_color = '\033[91m'
    blue_color = '\033[94m'
    reset = '\033[0m'

    print('\n' * pre_lines, end='')
    if header:
        print(red_color, '-' * 80, reset, sep='')
    if title:
        print(blue_color, title, reset, sep='')
    if footer:
        print(red_color, '-' * 80, reset, sep='')
    print('\n' * post_lines, end='')

# ------------------------------------------------------------------------------
# Manage the connection with server:
# ------------------------------------------------------------------------------


def connect_to_server(client_socket):
    """
    Connect to the server and complete initial setup phase.

    Returns:
        bool: True if the connection is successful, False otherwise.
    """

    try:
        client_socket.connect((SERVER_IP, SERVER_PORT))

        # R1 - Receive the welcome message from the server:
        handle_recv(*receive_message(client_socket), expected_topic='Hi')
        print('Connected to server successfully')

        # S1 - Send the device name to the server:
        handle_send(*send_message(client_socket,
                    topic="setup", message=DEVICE_NAME))
        print(f"Sent the device name  \t\t : '{DEVICE_NAME}'")

        # R2 - Receive the client-ID from the server:
        resp = handle_recv(
            *receive_message(client_socket), expected_topic='Client Id')
        MY_CLIENT_ID = resp["message"]
        print(f"Received client-ID \t\t : '{MY_CLIENT_ID}'")

        # R3 - Receive the class register form the server:
        resp = handle_recv(
            *receive_message(client_socket, save_folder=JSONS_FOLDER),
            expected_topic='Class Register')
        print(f"Received class register \t : '{resp['data']['filename']}'")

        # R4 - Get the models count and then models:
        resp = handle_recv(
            *receive_message(client_socket), expected_topic='Models Count')
        models_count = int(resp["message"])
        print(f"Received models count \t\t : '{models_count}'")

        # R5 - Get the models:
        print(f"Getting {models_count} models from the server :")
        for i in range(models_count):
            resp = handle_recv(
                *receive_message(client_socket, save_folder=MODELS_FOLDER),
                expected_topic='Pickle')
            print(f"\t - {resp['data']['filename']}")

        return True

    except Exception as e:
        return e

# ------------------------------------------------------------------------------
# Load balancing functions:
# ------------------------------------------------------------------------------


def static_load_balancing(client_socket):
    """Static load balancing logic."""

    # R1 - Receive the images count from the server:
    resp = handle_recv(*receive_message(client_socket),
                       expected_topic='Static Images Count')
    images_count = int(resp["message"])
    print(f"Total Image count : '{images_count}'")

    # Receive the images and return the responses:
    for i in range(images_count):
        # R2 - Receive the image from the server:
        resp = handle_recv(
            *receive_message(client_socket, save_folder=IMAGES_FOLDER),
            expected_topic='Static Image')

        image_time = resp["message"]
        image_name = resp["data"]["filename"]
        print(f"Received image \t : '{image_name}' of [{image_time}]")

        # Process the image:
        print(f"\t\t : Processing... ", end='\r')
        result = dummy_process_image(image_name)

        # Send the result back to the server:
        handle_send(*send_message(client_socket,
                    topic="Processed Data", message=json.dumps(result)))

    return True


def dynamic_load_balancing(client_socket):
    """Dynamic load balancing logic."""

    # The client can get any number of images from the server.
    while True:
        # R1 - Receive the image from the server:
        resp = handle_recv(
            *receive_message(client_socket, save_folder=IMAGES_FOLDER),
            expected_topic='Dynamic Task')

        # If 'message' is = 'done', it means all the images are processed:
        if resp["message"].lower() == "done":
            break

        image_time = resp["message"]
        image_name = resp["data"]["filename"]
        print(f"Received image \t : '{image_name}' of [{image_time}]")

        # Process the image:
        print(f"\t\t : Processing... ", end='\r')
        result = dummy_process_image(image_name)

        # Send the result back to the server:
        handle_send(*send_message(client_socket,
                    topic="Processed Data", message=json.dumps(result)))

    return True


# ------------------------------------------------------------------------------
# Dummy Image processing function:
# ------------------------------------------------------------------------------

def dummy_process_image(image_name):
    """Mock function to process an image and return JSON."""
    # Replace this with actual image processing logic
    import random
    time.sleep(random.randint(0, 5))
    return {"image_name": image_name, "status": "processed", "data": "some_data"}

# ------------------------------------------------------------------------------
# Main:
# ------------------------------------------------------------------------------


def main():
    # First prepare the necessary folders:
    prepare_folder(MODELS_FOLDER)
    prepare_folder(IMAGES_FOLDER)
    prepare_folder(JSONS_FOLDER)

    # Create a client socket:
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.settimeout(10)

    # Connect to the server and complete initial setup phase:
    print_header(pre_lines=0, post_lines=1, footer=False,
                 title='Connection Initialization Phase with server')

    resp = connect_to_server(client_socket=client_socket)
    if resp == True:
        print_header(
            pre_lines=1, post_lines=1, header=False,
            title='Connection Initialization phase with server successful.')
    else:
        raise Exception(resp)

    # Next phase:
    print_header(pre_lines=1, post_lines=1, footer=False,
                 title='Load Balancing Phase with server')

    # Get the mode of load balancing:
    resp = handle_recv(*receive_message(client_socket),
                       expected_topic='Load Balancing')
    load_balancing = resp["message"]
    print(f"`{load_balancing}` Load balancing mode selected.")

    # Load balancing phase:
    if load_balancing.lower() == "static":
        resp = static_load_balancing(client_socket)
    else:
        resp = dynamic_load_balancing(client_socket)

    if resp == True:
        print("All images processed successfully.")
        print_header(pre_lines=1, post_lines=1, header=False,
                     title='Load Balancing phase successful.')

    else:
        print(resp)

    # Close the client socket:
    print_header(pre_lines=1, post_lines=1,
                 title='Client\'s work is done. Closing the client socket 😊')
    client_socket.close()


# ------------------------------------------------------------------------------
# Entry point:
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
