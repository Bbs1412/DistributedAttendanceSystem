import os
import json
from threading import Lock
from datetime import datetime

logs = []
log_count = 1
log_lock = Lock()

log_file = os.path.join('logs.json')


def get_timestamp():
    return datetime.now().strftime('%Y-%m-%d_%I-%M-%S_%p')


def create_log(topic, message, status='Success', client_id=-1):
    global log_count
    log = {
        'id': log_count,
        'topic': topic,
        'message': message,
        'status': status,
        'client_id': int(client_id),
        'timestamp': get_timestamp()
    }

    logs.append(log)
    log_count += 1
    save_logs()


def get_log(log_id: int) -> dict:
    for log in logs:
        if log['id'] == log_id:
            return log
    return False


def get_log_after(log_id: int) -> list:
    """Get all logs after the given log_id"""
    logs_after = []
    for log in logs:
        if log['id'] > log_id:
            logs_after.append(log)
    return logs_after


def get_log_by_topic(topic: str) -> list:
    """Get all logs with the given topic"""
    logs_by_topic = []
    for log in logs:
        if topic in log['topic']:
            logs_by_topic.append(log)
    return logs_by_topic


def save_logs():
    # Acquire the lock before writing to the file
    with log_lock:
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=4)
