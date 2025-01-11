import os
import json
import base64
# import socket
import logger as l
from time import sleep
from datetime import datetime


# ------------------------------------------------------------------------------
# Base functions:
# ------------------------------------------------------------------------------

NO_DELAY = True


def procrastination_protocol(match_my_chill: int = None):
    if NO_DELAY:
        return
    AwkwardPauseTime = 1.0
    if match_my_chill:
        AwkwardPauseTime = match_my_chill
    sleep(AwkwardPauseTime)


def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d_%I-%M-%S_%p")


def clear_buffer(client_socket):
    print(f"{WARN} Clearing buffer...")
    client_socket.setblocking(False)
    try:
        while client_socket.recv(4096):
            pass
    except BlockingIOError:
        pass
    finally:
        client_socket.setblocking(True)


INFO = '\033[94m[INFO]\033[0m'
WARN = '\033[93m[WARN]\033[0m'
ERROR = '\033[91m[ERROR]\033[0m'

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
    def recv_all(sock, size):
        data = b""
        while len(data) < size:
            packet = sock.recv(size - len(data))
            if not packet:
                raise ConnectionError("Connection closed before all data was received.")
            data += packet
        return data
    
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
        # data = client_socket.recv(message_size)
        data = recv_all(client_socket, message_size)
        
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

            # print(f"{INFO} File saved: {file_path}")

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
                f"{WARN} Failed to recv / process message (Attempt [{current_attempt}/{max_attempts}]). Retrying...\n\t{e}"
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
        str: The error message if the message was not sent successfully, else an empty string.

    Note:
        There are two types of error handling in this function:
        1. Max attempts if error is purely on senders side
        2. Negative acknowledgment if error is on receiver side
    """
    procrastination_protocol()

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
            print(f"{WARN} Negative acknowledgment, sending again...")
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
                f"{ERROR} Received invalid acknowledgment while sending message."
            )

    except Exception as e:
        # Retry if attempts are remaining:
        if current_attempt < max_attempts:
            current_attempt += 1
            print(
                f"{WARN} Failed to send message in attempt [{current_attempt}/{max_attempts}]. Retrying... \n\t {e}")
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
            err = f"{ERROR} Failed to send message after {max_attempts} attempts.\n\t{e}"
            return False, err


# ------------------------------------------------------------------------------
# Helper functions for receive:
# ------------------------------------------------------------------------------


def handle_recv(status: bool, resp: dict | str, expected_topic: str,
                raise_exception: bool = True,
                log_topic: str = None, log_client_id: int = -1,
                log_success_message: str = ""):
    """ Handle the response from the receiver.

    Args:
        status (bool): The status of the response.
        resp (dict | str): The response received.
        expected_topic (str): The expected topic.
        raise_exception (bool, optional): Whether to raise an exception if the response is invalid.
        log_topic (str, optional): The topic to log.
        log_client_id (int, optional): The client ID to log.
        log_success_message (str, optional): The message to log on success.

    Raises:
        Exception: If the response is invalid and raise_exception is True.

    Returns:
        dict | str: The response if the response is valid, else an error-message if the response is invalid and raising exception is not allowed.
    """

    # True - Received successfully:
    if status:
        # Got what was expected:
        if resp["topic"] == expected_topic:
            if log_topic:
                l.create_log(topic=log_topic, message=log_success_message,
                             status="Success", client_id=log_client_id)
            return resp

        # Got wrong message:
        else:
            out_of_sync = "Server and client are out of sync...\n"
            out_of_sync += f"\t |─> [Expect] `{expected_topic}`\n"
            out_of_sync += f"\t ╰─> [Actual] `{resp['topic']}`"

            if log_topic:
                l.create_log(topic=log_topic, message=out_of_sync,
                             status="Error", client_id=log_client_id)

            # Raise exception if allowed, else, return the error message:
            if raise_exception:
                raise Exception(out_of_sync)
            else:
                return resp

    # False - Error in transmission even after all the retries:
    else:
        if log_topic:
            l.create_log(topic=log_topic, message=resp,
                         status="Error", client_id=log_client_id)

        # Raise exception if allowed, else, return the error message:
        if raise_exception:
            raise Exception(resp)
        else:
            return resp


# ------------------------------------------------------------------------------
# Helper functions for send:
# ------------------------------------------------------------------------------

def handle_send(status: bool, resp: str, raise_exception: bool = True,
                log_topic: str = None, log_client_id: int = -1,
                log_success_message: str = ""):
    """Handle the response from the sender.

    Args:
        status (bool): The status of the response.
        resp (str): The response received (err-msg or '').
        raise_exception (bool, optional): Whether to raise an exception if the response is invalid.
        log_topic (str, optional): The topic to log.
        log_client_id (int, optional): The client ID to log.
        log_success_message (str, optional): The message to log on success.

    Raises:
        Exception: If the response is invalid and raise_exception is True.

    Returns:
        bool: True if the response is valid, else error-message if the response is invalid and raising exception is not allowed.
    """

    # True - Sent successfully:
    if status:
        if log_topic:
            l.create_log(topic=log_topic, message=log_success_message,
                         status="Success", client_id=log_client_id)
        return True

    # False - Error in transmission even after all the retries:
    else:
        if log_topic:
            l.create_log(topic=log_topic, message=resp,
                         status="Error", client_id=log_client_id)

        # Raise exception if allowed, else, return the error message:
        if raise_exception:
            raise Exception(resp)
        else:
            return resp


# ------------------------------------------------------------------------------
# To check sender: (Put this in a separate file)
# ------------------------------------------------------------------------------


# import socket
# from networking import send_message, handle_send

# server_port = 12345
# server_ip = 'localhost'
# client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# print('Connecting to server...')
# client_socket.connect((server_ip, server_port))
# print('Connected to server!')
# print()

# # Actual:
# # status, resp = send_message(
# #     client_socket=client_socket,
# #     topic='test',
# #     message='Hello from the sender side!',
# #     # file_path='./networking.py'
# # )
# # resp = handle_send(status=status, resp=resp)

# # Or, shorter:
# resp = handle_send(
#     *send_message(
#         client_socket=client_socket,
#         topic='test',
#         message='Hello from the sender side!',
#         # file_path='./networking.py'
#     )
# )

# print(resp)


# ----------------------------------------------------------------------
# To check receiver: (Put this in a separate file)
# ----------------------------------------------------------------------


# import socket
# from networking import receive_message, handle_recv

# port = 12345
# server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# server_socket.bind(('localhost', port))
# server_socket.listen(5)
# print(f"Server started on port {port}")
# client_socket, addr = server_socket.accept()
# print(f"Connection from {addr}\n")

# # Actual:
# # status, resp = receive_message(
# #     client_socket=client_socket,
# #     save_folder='Images'
# # )
# # resp = handle_recv(status=status, resp=resp, expected_topic='test')

# # Or shorter:
# resp = handle_recv(
#     *receive_message(client_socket=client_socket,
#                      save_folder='Images'),
#     expected_topic='test'
# )

# print(resp)
