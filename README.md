# Distributed Attendance System
This is the distributed processing version of the [Smart Attendance System](https://github.com/Bbs1412/SmartAttendanceSystem) project, utilizing distributed processing for attendance calculation through face recognition. 

<!-- [![Project Repo](https://img.shields.io/badge/Repository-%20Smart%20Attendance%20System-blue.svg?style=flat&logo=github)](https://github.com/Bbs1412/SmartAttendanceSystem) -->


## Index:
- [Distributed Attendance System](#distributed-attendance-system)  
- [Project Overview](#-project-overview)
    - [Aim](#aim)
    - [Methodology](#methodology)
    - [Features](#features)
    - [Tech Stack](#tech-stack)
- [Steps to run](#-steps-to-run)
    - [Server Setup](#server-setup)
    - [Client Setup](#client-setup)
- [Contributions](#-contributions)
- [License](#-license)
- [Contact](#-contact)


## 🎯 Project Overview:
### Aim:
+ Leverage the power of multiple clients to process video frames for attendance marking using face recognition.
+ Implement both Static and Dynamic load balancing for efficient processing and faster results.

### Methodology:
1. **Server Initialization:**
   - A web server starts the distributed server, which connects to multiple clients (as configured in the `.env` file).
   - Initialization includes:
        - Accepting client connections and registering their details.
        - Sending pre-trained face models and essential files to each client.
        - <video src="https://github.com/user-attachments/assets/b2e9ed9d-05fb-46c0-a61f-d715a3b6eacb" type="video/mp4" alt="Server-Initialization-Video"></video> 
        - Setting clients on standby mode for task distribution.
        - <video src="https://github.com/user-attachments/assets/ef51f1ba-2109-4f6d-b57e-3d4163b8a152" type="video/mp4" alt="Client-Initialization-Video"></video>

2. **Task Distribution:**
   - The server accepts video uploads from the frontend.
   - Tasks are assigned to clients based on the selected load balancing mode:
        1. **`Static Load Balancing:`** 
            - Tasks are evenly distributed before processing begins. 
            - All clients must finish their tasks before results can be combined.
            - <video src="https://github.com/user-attachments/assets/9f61a92c-ce0d-4480-98b5-35b1639962db" type="video/mp4" alt="Client-Static-Load-Balancing-Video"></video>
            - Means, the server has to wait for all clients to complete the task.
            - <video src="https://github.com/user-attachments/assets/839c4cac-8e77-4eb1-8ef3-89ecf6e9e995" type="video/mp4" alt="Server-Static-Load-Balancing-Video"></video>

        2. **`Dynamic Load Balancing:`** 
            - Tasks are assigned based on client processing speed in real-time, ensuring efficient resource utilization.
            - <video src="https://github.com/user-attachments/assets/b369b03d-db8d-4b13-91a4-e9a26de1d0ca" type="video/mp4" alt="Client-Dynamic-Load-Balancing-Video"></video>
            - All the clients finish the task approximately at the same time.
            - <video src="https://github.com/user-attachments/assets/07fa6f98-ebea-447a-a8dc-00b7452480d0" type="video/mp4" alt="Server-Dynamic-Load-Balancing-Video"></video>

3. **Processing:**
   - Clients process video frames using OpenCV and `face_recognition`.
   - Results are returned to the server.
   - Separate results from clients are combined, and rendered as attendance data.

4. **Output:**
   - Results are displayed on a web page and can be downloaded in Excel format as well.


### Features:
- **Web-based Interface:** Upload videos and view/download attendance results.
- **Parallel Processing:** Faster processing through distributed clients.
- **Customizable Load Balancing:** Switch between static and dynamic modes.
- Thread locking for consistent read-write operations.
- **Accurate Attendance Marking:** Threshold-based attendance marking ensures precision.
- **Detailed Reporting:** Faculty can access detailed results and downloadable attendance records.


### Tech Stack:
+ **Backend:** Python, Flask
+ **Frontend:** HTML, CSS, JavaScript
+ **Libraries:** OpenCV, face_recognition, threading, socket
+ **Data Formats:** JSON, Excel
+ **Tools:** Virtual environment (venv), Python's standard libraries

---

## 🚀 Steps to run:

### Server Setup:
1. Clone the repository:
    ```bash
    git clone --depth 1 https://github.com/Bbs1412/DistributedAttendanceSystem.git
    ```
    
1. Navigate to the project directory:
    ```bash
    cd DistributedAttendanceSystem
    ```

1. Create a virtual environment and install dependencies:
    ```bash
    python -m venv venv
    venv\Scripts\activate
    pip install -r "requirements_all.txt"
    ```

1. Configure the number of clients in the `.env` file:
    ```js
    no_of_clients = 2
    ```

1. Train the face recognition models:
    - Create a folder named `Pics` in the project directory and add the images of the people you want to recognize in the `Pics` folder.
    - Update the ***people*** list in `face_train.py` (~line 73)::
        ```Python
        Person(
            reg='registration_number',
            name='Name',
            image='person_name.jpg',      # Image should be in the 'Pics' folder
            display_name='Display Name',  # optional
            pickle_name='person_name.pkl' # optional
        )
        ```
    - Run the training script:
        ```bash
        python face_train.py
        ```

1. Start the web server:
    ```bash
    python app.py
    ```

1. Connect clients:
    - Run the `distributed_client.py` on all the clients within span of set timeout.

7. Open the browser at:
    ```plaintext
    http://localhost:5000
    ```

### Client Setup:
1. Clone the repository:
    ```bash
    git clone --depth 1 https://github.com/Bbs1412/DistributedAttendanceSystem.git
    ```

1. Copy `networking.py` and `logger.py` from the root directory to `Client/` directory.

1. Navigate to the client directory:
    ```bash
    cd DistributedAttendanceSystem/Client
    ```

1. Create a virtual environment and install dependencies:
    ```bash
    python -m venv venv
    venv\Scripts\activate
    cp ../requirements_all.txt .
    pip install -r "requirements_all.txt"
    ```

1. Rest all files outside `Client/` can be deleted.

1. Run the client once main server is up:
    ```bash
    python distributed_client.py
    ```

1. Repeat the above steps for all the clients.

---

## 🤝 Contributions:
   Any contributions or suggestions are welcome! 


## 📜 License: 
[![Code-License](https://img.shields.io/badge/License%20-GNU%20--%20GPL%20v3.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
- This project is licensed under the `GNU General Public License v3.0`
- See the [LICENSE](LICENSE) file for details.
- You can use the code with proper credits to the author.


## 📧 Contact:
- **Email -** [bhushanbsongire@gmail.com](mailto:bhushanbsongire@gmail.com)


---
<!-- keep this:
+ Web server at starts a separate distributed server.
+ Distributed server first connects to multiple clients (which can be adjusted dynamically in the .env file) for processing the video.
+ Initialization phase is completed first:
  <details open>
    <summary>Expand for details</summary>
    <ul> 
      <li> Client connection it accepted and name is sent   to server. </li>
      <li> Pre trained face models are sent to client. </li>
      <li><video width="100%" controls src="https://github.com/user-attachments/assets/ef51f1ba-2109-4f6d-b57e-3d4163b8a152" type="video/mp4"></li>
    </ul>
  </details> 
+ as some
-->