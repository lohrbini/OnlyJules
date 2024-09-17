FROM python:3-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Make port 8000 available to the world outside this container
RUN apt update && \
    apt install libgl1-mesa-glx libglib2.0-0 libsm6 libxrender1 libxext6 -y && \
    python3 -m pip install -r requirements.txt && \
    mkdir /database

EXPOSE 5000

# Run the application
CMD ["python3", "app.py"]
