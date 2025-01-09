import os
import json
import socket
import threading
from datetime import datetime
from dotenv import load_dotenv

import logger as l
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
    print(f"{INFO} Server shut down.")
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
            args=(client_socket, client_address),
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
    print(f"{INFO} All clients released.")
    l.create_log(topic='Connection', status='Info', client_id=-1,
                 message="All clients released.")


def handle_client_initialization(client_socket, client_address):
    """Handle initial communication with a client."""
    global clients
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

        print(f"{INFO} Client {client_id} : Connected Successfully {client_address}")

        # S1 - Send welcome message to client:
        handle_send(*send_message(client_socket, topic='Hi'),
                    log_topic='Connection - Welcome', log_client_id=client_id,
                    log_success_message='Client welcome message sent successfully.')

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

        # S2 - Send client ID assigned to the client:
        handle_send(
            *send_message(client_socket, topic='Client Id', message=client_id),
            log_topic='Connection - Client Info',
            log_client_id=client_id, log_success_message=client_name)

        # S3 - Send class file to the client:
        handle_send(*send_message(
            client_socket, topic='Class Register', file_path=CLASS_REGISTER),
            log_client_id=client_id, log_topic='Initialization - Class Register',
            log_success_message='Class register sent successfully.')

        # S4 - Send the model count first to client:
        count = str(len(os.listdir(MODELS)))
        handle_send(
            *send_message(client_socket, topic='Models Count', message=count),
            log_topic='Initialization - Models Count', log_client_id=client_id,
            log_success_message='Model count sent successfully.')

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

        print(f"{INFO} Client {client_id} : Image {i:02d} - [{timestamp}] sent.")

        # R1 - Receive the processed data from the client:
        resp = handle_recv(
            *receive_message(client_socket), expected_topic='Processed Data',
            log_topic='Load Balancing - Processed Data', log_client_id=client_id,
            log_success_message=f'Image {i} - [{timestamp}] processed successfully.')

        # Save the response:
        processed_data = json.loads(resp['message'])
        append_response(processed_data)

    print(f"{INFO} Client {client_id} :  All Image Processing completed.")


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
# Main driver part:
# ------------------------------------------------------------------------------


def main():
    global server_socket
    server_socket = start_server()

    # Get all the clients connected to the server
    get_clients()

    if input(f"{WARN} Press Enter to start the load balancing strategy...") != '':
        print(f"{WARN} Load balancing aborted. Exiting...")
        exit()

    # Start the attendance calculation with decided load balancing strategy:
    start_load_balancing()

    # Compile the results here only or hand it over to the main flask server
    ...

    # Close all client sockets and the server socket
    release_clients()
    stop_server()


# ------------------------------------------------------------------------------
# Entry point: (Can run this for testing)
# Otherwise comment this part below before deploying.
# The web-server will import required functions from this file.
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
