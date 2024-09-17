# flaskStreamR

**flaskStreamr** is a web application designed for managing and viewing RTSP camera streams. It provides an easy-to-use interface for monitoring multiple camera feeds and managing camera settings. 

## Features

- **Camera Overview**: View snapshots and live feeds from multiple RTSP cameras.
- **Add and Update Cameras**: Add new cameras and update existing ones with new IPs, ports, paths, and credentials.
- **User Management**: Manage user accounts and view last login information.
- **Change Password**: Securely change user passwords.
- **Theming**: Switch between light and dark modes for better visual comfort.

## Installation

To set up flaskStreamr on your local machine, follow these steps:

1. **Clone the Repository**

   ```bash
   https://github.com/lohrbini/flaskStreamr.git
   cd flaskStreamr

2. **Run the Application**

To run the application in docker use this command

```
docker run -v ./database:/database --network host -p 5000:5000 -d harbor.skl.works/library/flaskstreamr:v0.0.1 
```

Otherwise install the pip packages and run the Application without docker

```
python3 -m pip install -r requirements.txt
python3 app.py
```

3. **Access the Application**
The application is now reachable at `http://localhost:5000`
