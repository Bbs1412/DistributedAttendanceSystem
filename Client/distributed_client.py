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

os.makedirs(MODELS_FOLDER, exist_ok=True)
os.makedirs(IMAGES_FOLDER, exist_ok=True)
os.makedirs(JSONS_FOLDER, exist_ok=True)

MY_CLIENT_ID = None
LOGS = []

file_save_lock = threading.Lock()

# ------------------------------------------------------------------------------
# Utility functions:
# ------------------------------------------------------------------------------


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
        print(red_color, '-'*80, reset, sep='')
    if title:
        print(blue_color, title, reset, sep='')
    if footer:
        print(red_color, '-'*80, reset, sep='')
    print('\n' * post_lines, end='')

# ------------------------------------------------------------------------------
# Manage the connection with server:
# ------------------------------------------------------------------------------


def out_of_sync():
    # raise error :  'Server and client are out of sync...'
    raise Exception("Server and client are out of sync...")


def connect_to_server(client_socket):
    """
    Connect to the server and complete initial setup phase.

    Returns:
        bool: True if the connection is successful, False otherwise.
    """

    try:
        client_socket.connect((SERVER_IP, SERVER_PORT))

        # R1 - Receive the welcome message from the server:
        resp = receive_message(client_socket)
        if resp['topic'] != 'Hi':
            out_of_sync()
        print('Connected to server successfully')

        # S1 - Send the device name to the server:
        send_message(client_socket, topic="setup", message=DEVICE_NAME)
        print(f"Sent the device name  \t\t : '{DEVICE_NAME}'")

        # R2 - Receive the client-ID from the server:
        resp = receive_message(client_socket)
        if resp["topic"] != "Client Id":
            out_of_sync()
        MY_CLIENT_ID = resp["message"]
        print(f"Received client-ID \t\t : '{MY_CLIENT_ID}'")

        # S2 - Send 'OK' to the server:
        send_message(client_socket, topic="OK")

        # R3 - Receive the class register form the server:
        resp = receive_message(client_socket, save_folder=JSONS_FOLDER)
        if resp["topic"] != "Class Register":
            out_of_sync()
        print(f"Received class register \t : '{resp['data']['filename']}'")

        # S3 - Send 'OK' to the server:
        send_message(client_socket, topic="ACK")

        # R4 - Get the models count and then models:
        resp = receive_message(client_socket)
        if resp["topic"] != "Models Count":
            out_of_sync()
        models_count = int(resp["message"])
        print(f"Received models count \t\t : '{models_count}'")

        # S5 - Send 'Ready' to the server:
        send_message(client_socket, topic="Ready")

        # R5 - Get the models:
        print(f"Getting {models_count} models from the server :")
        for i in range(models_count):
            resp = receive_message(client_socket, save_folder=MODELS_FOLDER)
            if resp["topic"] != "Pickle":
                out_of_sync()

            print(f"\t - {resp['data']['filename']}")

            # Ack the model received:
            send_message(client_socket, topic="Received")

        return True

    except Exception as e:
        return e

# ------------------------------------------------------------------------------
# Load balancing functions:
# ------------------------------------------------------------------------------


def static_load_balancing(client_socket):
    """Static load balancing logic."""
    try:
        # R1 - Receive no of images to process from the server:
        resp = receive_message(client_socket)
        if resp["topic"] != "Static Images Count":
            out_of_sync()

        images_count = int(resp["message"])
        print(f'Received Image Count \t : {images_count}')
        print(f'Started Processing \t :')

        # S1 - Send 'Ready' to the server:
        send_message(client_socket, topic="Ready")

        # R2 - Get the images and timestamps from the server:
        for i in range(images_count):
            # R2 - Get the image, timestamp:
            resp = receive_message(client_socket, save_folder='Images')
            if resp["topic"] != "Static Image":
                out_of_sync()

            image_name = resp["data"]["filename"]
            timestamp = resp["message"]

            # S2 - Send 'Received' to the server:
            send_message(client_socket, topic="Received Image")
            print(f'\t + {i} - {image_name} \t - Received - ', end='')

            # Process the image:
            json_data = process_image(image_name)
            print('Processed')
            append_log(json_data)

            # S3 - Send the processed data back to the server:
            send_message(client_socket, topic="Processed Data",
                         message=json.dumps(json_data))

        # R3 - Receive 'End' from the server:
        resp = receive_message(client_socket)
        if resp["topic"] != "End":
            out_of_sync()

        return True
    except Exception as e:
        return e


def dynamic_load_balancing(client_socket):
    """Dynamic load balancing logic."""
    try:
        ...
        return True

    except Exception as e:
        return e


def process_image(image_name):
    """Mock function to process an image and return JSON."""
    # Replace this with actual image processing logic
    time.sleep(2.5)
    return {"image_name": image_name, "status": "processed", "data": "some_data"}

# ------------------------------------------------------------------------------
# Main:
# ------------------------------------------------------------------------------


def main():
    # Create a client socket:
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.settimeout(10)

    # Connect to the server and complete initial setup phase:
    print_header(pre_lines=0, post_lines=1, footer=False,
                 title='Connection Initialization Phase with server')

    resp = connect_to_server(client_socket=client_socket)
    if resp == True:
        print_header(pre_lines=1, post_lines=1, header=False,
                     title='Connection Initialization phase with server successful.')
    else:
        print(resp)
        return

    # Next phase:
    print_header(pre_lines=1, post_lines=1, footer=False,
                 title='Load Balancing Phase with server')

    # Get the mode of load balancing:
    resp = receive_message(client_socket)
    if resp["topic"] != "Load Balancing":
        out_of_sync()

    # 'ACK' the server:
    send_message(client_socket, topic="ACK")
    load_balancing = resp["message"]

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
        return


# ------------------------------------------------------------------------------
# Entry point:
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
