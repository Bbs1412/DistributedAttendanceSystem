import os
import json
import socket
import threading
import logger as l
from datetime import datetime
from dotenv import load_dotenv

from Client.networking import receive_message, send_message


# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------


load_dotenv()
CLASS_REGISTER = os.environ.get('class_register')
UPLOADS = os.environ.get('upload_folder')
MODELS = os.environ.get('face_models_folder')
UPLOADED_DATA = os.environ.get('uploaded_data')
ATTENDANCE_LOG_FILE = os.environ.get('attendance_raw_file')
ATTENDANCE_REGISTER = os.environ.get('class_attendance')

HOST = '127.0.0.1'
PORT = 12345
TIMEOUT = 8
NO_OF_CLIENTS = 1

# Shared state
clients = {}
# 'sample_client_3': {
#     'name': 'Sample Client',
#     'socket': "python_data",
#     'address': "192.168.13.12"
# }

for i in range(NO_OF_CLIENTS):
    clients[str(i+1)] = None

lock = threading.Lock()
responses = []


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

def handle_error(client_id, error, topic):
    l.create_log(
        topic=topic,
        message=error,
        status='Error',
        client_id=client_id
    )
    raise Exception(error)


def handle_client_initialization(client_socket, client_address):
    """Handle initial communication with a client."""

    try:
        client_id = 0
        client_name = 'Unresolved'

        # Dynamically assign the first available client_id:
        for i in range(NO_OF_CLIENTS):
            cid = str(i+1)
            if clients[cid] == None:
                # Assign that client-id
                client_id = cid
                # Block that client-id temporarily (else concurrency issues might occur)
                clients[cid] = 'hold'

        print(
            f"[INFO] Client {client_id} : Connected Successfully {client_address}")

        # S1 - Send welcome message
        send_message(client_socket, topic='Hi')

        # R1 - Receive client name
        resp = receive_message(client_socket)
        if resp['topic'] != 'setup':
            handle_error(client_id=client_id, topic='Connection',
                         error="Client didn't send the setup message.")

        client_name = resp['message']

        # Update the shared state:
        clients[client_id] = {
            "name": client_name,
            "socket": client_socket,
            "address": client_address
        }

        # S2 - Send client ID
        send_message(client_socket, topic='Client Id', message=client_id)

        # Log the connection:
        l.create_log(
            topic='Connection',
            message=f'Client {client_id} - `{client_name}` connected',
            status='Success',
            client_id=client_id
        )

        # R2 - Receive the 'OK' from the client
        resp = receive_message(client_socket)
        if resp['topic'] != 'OK':
            handle_error(client_id=client_id, topic='Connection',
                         error="Client didn't acknowledge the connection.")

        # S3 - Send class file
        send_message(client_socket, topic='Class Register',
                     file_path=CLASS_REGISTER)

        # R3 - Check for 'ACK' from the client:
        resp = receive_message(client_socket)
        if resp['topic'] != 'ACK':
            handle_error(client_id=client_id, topic='Initialization',
                         error="Client didn't acknowledge the class register.")

        l.create_log(
            topic='Initialization',
            message=f'Sent class register to Client {client_id}',
            status='Success',
            client_id=client_id
        )

        # S4 - Send the model count first and then the models
        count = len(os.listdir(MODELS))
        send_message(client_socket, topic='Models Count', message=str(count))

        # R4 - Check if client is 'ready':
        resp = receive_message(client_socket)
        if resp['topic'] != 'Ready':
            handle_error(client_id=client_id, topic='Initialization',
                         error="Client didn't acknowledge the models.")

        # S5 - Send the models
        for i, file in enumerate(os.listdir(MODELS)):
            file_path = os.path.join(MODELS, file)
            send_message(client_socket, topic='Pickle', file_path=file_path)

            resp = receive_message(client_socket)
            if resp['topic'] != 'Received':
                handle_error(client_id=client_id, topic='Initialization',
                             error=f"Client didn't acknowledge the model {i} - '{file_path}' received.")

        l.create_log(
            topic='Initialization',
            message=f'Sent all the face models to Client {client_id}',
            status='Success',
            client_id=client_id
        )

        # Mark end of initialization phase
        msg = f"[INFO] Client {client_id} : Initialization phase completed."
        print(msg)
        l.create_log(
            topic='Initialization',
            message=msg,
            status='Success',
            client_id=client_id
        )

    except Exception as e:
        l.create_log(
            topic='Connection',
            message=f'Client {client_id} - `{client_name}` connection error: {e}',
            status='Error',
            client_id=client_id
        )
        print(
            f"[ERROR] Client {client_id} Initialization Error \n\t{e}")


# ------------------------------------------------------------------------------
# Load balancing strategies:
# ------------------------------------------------------------------------------


def static_mode_thread(image_list, timestamp_list, client_id):
    """Threaded function to handle the static load balancing."""
    client_socket = clients[str(client_id)]['socket']
    client_name = clients[str(client_id)]['name']

    # S0 - Inform client the mode of operation:
    send_message(client_socket, topic='Load Balancing', message='Static')

    # R0 - Receive the 'ACK' from the client
    response = receive_message(client_socket)
    if response['topic'] != 'ACK':
        handle_error(client_id=client_id, topic='Load Balancing',
                     error="Client didn't acknowledge the load balancing mode.")

    # S1 - Send the image count to the client:
    send_message(client_socket, topic='Static Images Count',
                 message=len(image_list))

    # R1 - Receive the 'Ready' from the client
    response = receive_message(client_socket)
    if response['topic'] != 'Ready':
        handle_error(client_id=client_id, topic='Load Balancing',
                     error="Client didn't acknowledge the image count.")

    # Send the images and timestamps to get response:
    for i, (image, timestamp) in enumerate(zip(image_list, timestamp_list)):
        # S2 - Send the image and timestamp
        send_message(client_socket, topic='Static Image',
                     message=timestamp, file_path=image)

        # R2 - Check for ACK from the client:
        response = receive_message(client_socket)
        if response['topic'] != 'Received Image':
            handle_error(client_id=client_id, topic='Load Balancing',
                         error=f"Client didn't acknowledge the image {i} - '{image}' received.")

        l.create_log(
            topic='Load Balancing',
            message=f'Sent image {i} to Client {client_id}',
            status='Info',
            client_id=client_id
        )

        # R3 - Receive the response from the client
        response = receive_message(client_socket)
        if response['topic'] != 'Processed Data':
            handle_error(client_id=client_id, topic='Load Balancing',
                         error=f"Client didn't process the image {i} - '{image}'.")

        # Save the response
        processed_data = json.loads(response['message'])
        append_response(processed_data)

        l.create_log(
            topic='Load Balancing',
            message=f'Processing image {i} from Client {client_id} completed',
            status='Success',
            client_id=client_id
        )

    # S3 - Send the 'End' message to the client
    send_message(client_socket, topic='End')

    print(f"[INFO] Client {client_id} :  All Processing completed.")


def static_mode(image_files, timestamps, frames_count):
    """Static load balancing strategy."""
    print("[INFO] Static mode selected. Starting static load balancing...")

    per_client = frames_count // NO_OF_CLIENTS

    divided_data = [{
        "images": image_files[i*per_client: i*per_client + per_client],
        "timestamps": timestamps[i*per_client: i*per_client + per_client],
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

    print("[INFO] Static load balancing completed.")


def dynamic_mode(client_sockets):
    ...

# ------------------------------------------------------------------------------
# Main driver part:
# ------------------------------------------------------------------------------


def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.settimeout(20)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"[INFO] Server started at `{HOST}:{PORT}`")

    l.create_log('Server', f"Server started at `{HOST}:{PORT}`", 'Success')
    server_socket.settimeout(TIMEOUT)

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

    print(
        f"[INFO] All {NO_OF_CLIENTS} clients connected. Starting load balancing...")

    # Read the uploaded_data json file:
    with open(UPLOADED_DATA, 'r') as f:
        data = json.load(f)

    image_files = data['files']
    timestamps = data['js_mod']
    frames_count = data['frame_count']
    processing_mode = data['processing_mode']

    # Start the load balancing strategy
    if processing_mode.lower() == 'static':
        l.create_log(
            topic='Load Balancing',
            message='Static mode selected. Starting static load balancing...',
            status='Info'
        )
        static_mode(image_files, timestamps, frames_count)

    elif processing_mode.lower() == 'dynamic':
        l.create_log(
            topic='Load Balancing',
            message='Dynamic mode selected. Starting dynamic load balancing...',
            status='Info'
        )
        dynamic_mode(image_files, timestamps, frames_count)

    else:
        handle_error(client_id=-1, topic='Load Balancing',
                     error="Invalid mode selected. Exiting...")

    # Close all client sockets and the server socket
    for client_socket in client_sockets:
        client_socket.close()
    server_socket.close()
    print("[INFO] Server shut down.")


# ------------------------------------------------------------------------------
# Entry point:
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
