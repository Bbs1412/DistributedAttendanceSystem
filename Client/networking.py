# Modify send fn just like recv to return error and status to the caller and not to take things in own hands

import socket
import os
import json
import base64
from datetime import datetime


# ------------------------------------------------------------------------------
# Base functions:
# ------------------------------------------------------------------------------

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d_%I-%M-%S_%p")


def clear_buffer(client_socket):
    print("Started clear buffer")
    client_socket.setblocking(False)
    try:
        while client_socket.recv(4096):
            pass
    except BlockingIOError:
        pass
    finally:
        client_socket.setblocking(True)
        print("Exited clear buffer")


# ------------------------------------------------------------------------------
# Main functions:
# ------------------------------------------------------------------------------

def receive_message(
    client_socket, save_folder=None, max_attempts: int = 3, current_attempt: int = None
):
    """Receive a message from one host to another using the given socket.

    Args:
        client_socket (socket): The socket object to use for receiving the message.
        save_folder (str): The folder to save the file to.
        max_attempts (int): The maximum number of attempts to receive the message.
        current_attempt (int): The current attempt number.

    Returns:
        bool: True if the message was received successfully, False otherwise.
        dict: The message received

    Note:
        There's way of error handling in this function:
        If there's an error, 'NACK' is sent back to the sender max 'max_attempts' times. Sender is designed to retry if 'NACK' is received.
    """
    if current_attempt is None:
        current_attempt = 0

    try:
        # Read the message size
        message_size_bytes = client_socket.recv(4)
        if not message_size_bytes:
            raise ValueError("Failed to read message size.")

        message_size = int.from_bytes(message_size_bytes, "big")
        if message_size <= 0:
            raise ValueError("Invalid message size.")

        # Read the actual message
        data = client_socket.recv(message_size)
        if not data:
            raise ValueError("No data received.")

        # Parse the JSON message
        response = json.loads(data.decode("utf-8"))

        # Save file if applicable
        if save_folder and ("data" in response) and ("file" in response["data"]):
            filename = response["data"]["filename"]
            file_data = base64.b64decode(response["data"]["file"])

            os.makedirs(save_folder, exist_ok=True)
            file_path = os.path.join(save_folder, filename)

            with open(file_path, "wb") as file:
                file.write(file_data)

            print(f"[INFO] File saved: {file_path}")

        # Send the 'ACK' message back:
        msg = "ACK"
        client_socket.sendall(msg.encode("utf-8"))

        return True, response

    except Exception as e:
        # Retry if attempts are remaining using 'NACK':
        if current_attempt < max_attempts:
            client_socket.sendall(b"NACK")
            current_attempt += 1
            print(
                f"[WARNING] Failed to recv / process message \
                    (Attempt [{current_attempt}/{max_attempts}]). Retrying...\n\t{e}"
            )

            clear_buffer(client_socket)

            return receive_message(
                client_socket=client_socket,
                save_folder=save_folder,
                max_attempts=max_attempts,
                current_attempt=current_attempt,
            )

        else:
            err = f"Failed to receive message after {max_attempts} attempts.\n\t{e}"
            return False, err


def send_message(
    client_socket,
    topic: str,
    message: str = None,
    file_path: str = None,
    max_attempts: int = 3,
    current_attempt: int = None,
):
    """Send a message from one host to another using the given socket.

    Args:
        client_socket (socket): The socket object to use for sending the message.
        topic (str): The topic of the message.
        message (str): The message to send.
        file_path (str): The path to the file to send.
        max_attempts (int): The maximum number of attempts to send the message.
        current_attempt (int): The current attempt number.

    Returns:
        bool: True if the message was sent successfully, False otherwise.
        str: The error message if the message was not sent successfully.

    Note:
        There are two types of error handling in this function:
        1. Max attempts if error is purely on senders side
        2. Negative acknowledgment if error is on receiver side
    """
    if current_attempt is None:
        current_attempt = 0

    try:
        # Construct the JSON message
        to_send = {
            "topic": topic,
            "timestamp": get_timestamp(),
        }

        # Attach file data if provided
        if file_path:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            with open(file_path, "rb") as file:
                # Read the file data
                file_data = file.read()
                # Encode bin -> base64
                file_data = base64.b64encode(file_data)
                # Convert to string
                file_data = file_data.decode("utf-8")

            to_send["data"] = {
                "file": file_data,
                "filename": os.path.basename(file_path),
            }

        # Attach additional message
        if message:
            to_send["message"] = message

        # Convert to JSON and send
        json_message = json.dumps(to_send).encode("utf-8")
        client_socket.sendall(len(json_message).to_bytes(4, "big"))
        client_socket.sendall(json_message)

        # Get the 'ACK' response
        response = client_socket.recv(4).decode("utf-8")
        if response == "ACK":
            return True, ""

        elif response == "NACK":
            print(f"[INFO] Negative acknowledgment, sending again...")
            return send_message(
                client_socket=client_socket,
                topic=topic,
                message=message,
                file_path=file_path,
                max_attempts=max_attempts,
                current_attempt=current_attempt,
            )

        else:
            print(response)
            raise ValueError(
                "[Error] Received invalid acknowledgment while sending message."
            )

    except Exception as e:
        # Retry if attempts are remaining:
        if current_attempt < max_attempts:
            current_attempt += 1
            print(
                f"""
                [Warning] Failed to send message in attempt 
                [{current_attempt}/{max_attempts}]. Retrying... \n\t {e}
                """
            )
            return send_message(
                client_socket=client_socket,
                topic=topic,
                message=message,
                file_path=file_path,
                max_attempts=max_attempts,
                current_attempt=current_attempt,
            )

        # Ran out of attempts, return error to calling function:
        else:
            err = (
                f"[ERROR] Failed to send message after {max_attempts} attempts.\n\t{e}"
            )
            return False, err


# ------------------------------------------------------------------------------
# Helper functions for receive:
# ------------------------------------------------------------------------------

def out_of_sync(expected_topic: str, recv_topic: str):
    exc = "Server and client are out of sync...\n"
    exc += f"\t |─> [Expect] `{expected_topic}`\n"
    exc += f"\t ╰─> [Actual] `{recv_topic}`"
    raise Exception(exc)


def handle_recv(status: bool, resp: dict | str, expected_topic: str):
    # True - Received successfully:
    if status:
        # Got what was expected:
        if resp["topic"] == expected_topic:
            return resp
        # Got wrong message:
        else:
            out_of_sync(expected_topic, resp["topic"])
    # False - Error in transmission even after all the retries:
    else:
        raise Exception(resp)


# ------------------------------------------------------------------------------
# Helper functions for send:
# ------------------------------------------------------------------------------

def handle_send():
    ...

# ------------------------------------------------------------------------------
# To check sender: (Put this in a separate file)
# ------------------------------------------------------------------------------

# server_port = 12345
# server_ip = 'localhost'
# client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# print('Connecting to server...')
# client_socket.connect((server_ip, server_port))
# print('Connected to server!')
# print()

# status, err = send_message(
#     client_socket=client_socket,
#     topic='test',
#     message='Hello from the sender side!',
#     file_path='./face_train.py'
# )

# if status:
#     print('Message sent successfully!')
# else:
#     print(err)


# ----------------------------------------------------------------------
# To check receiver: (Put this in a separate file)
# ----------------------------------------------------------------------

# port = 12345
# server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# server_socket.bind(('localhost', port))
# server_socket.listen(5)
# print(f"Server started on port {port}")
# client_socket, addr = server_socket.accept()
# print(f"Connection from {addr}")

# status, resp = receive_message(
#     client_socket=client_socket, save_folder="./excels")
# if status:
#     print(f"[INFO] Message received successfully:")
#     print(json.dumps(resp, indent=4))
# else:
#     print(resp)
