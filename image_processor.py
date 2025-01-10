import os
import json
import time
import base64
from datetime import datetime
from dotenv import load_dotenv
from typing import Union, List

load_dotenv()
# print(static_url)


def get_py_stamp(js_timestamp: str):
    """
    Convert js timestamp to py timestamp
    """
    dt_timestamp = datetime.strptime(js_timestamp, "%d/%m/%Y, %I:%M:%S %p")
    py_timestamp = dt_timestamp.strftime("%Y-%m-%d_%Hh%Mm%Ss")
    return py_timestamp


def process_image(timestamps: Union[list, str], base64s: Union[list, str]):
    """
    Takes js timestamps and base64s
    Converts into py stamps, and also, saves the images
    Returns modified js stamps with _1, _2 etc. as well
    """
    curr_stamp = datetime.now()
    py_time_stamps = []
    js_modified_time_stamps = []
    file_names = []

    # Issues is that, when multiple frames under same second are passed, out naming scheme does not support that
    # Means, the same name is returned by function and only one image is over-written again n again with that PARTICULAR name.
    # So keeping the last saved name in memory to add some _1 _2 after the repeated names.
    last_saved = ""
    same_name_count = 0

    # with open("formData.json", 'w') as f:
    #     f.write(json.dumps({'timestamps': timestamps, 'bases': base64s}))

    for timestamp, base64_str in zip(timestamps, base64s):

        # get the extension from: "data:image/jpeg;base64,full_base64_string"
        extension = base64_str.split(',')[0].split('/')[1].split(';')[0]
        # remove that part: "data:image/jpeg;base64"
        image_data = base64.b64decode(base64_str.split(',')[1])

        upload_folder = os.environ.get("upload_folder")
        folder = f'{curr_stamp.strftime("%Y-%m-%d_%Hh%Mm%Ss")}'
        folder = os.path.join(upload_folder, folder)
        os.makedirs(folder, exist_ok=True)

        file_base_name = get_py_stamp(timestamp)

        if file_base_name == last_saved:
            same_name_count += 1
            # file_base_name += f'_{same_name_count}'
        else:
            last_saved = file_base_name
            same_name_count = 0

        # Irrespective of the above if-else, always append the count
        # Maintains same filename-length for all images
        file_base_name += f'_{same_name_count:02d}'
        js_modified_time_stamps.append(f"{timestamp}, {same_name_count}")

        file_name = f'{file_base_name}.{extension}'
        file_path = os.path.join(folder, file_name)

        py_time_stamps.append(file_base_name)
        file_names.append(file_path)

        with open(file_path, 'wb') as f:
            f.write(image_data)

        # print(f'Saved image `{file_name}` successfully...')
    return file_names, py_time_stamps, js_modified_time_stamps
# process_image(timestamps, )
