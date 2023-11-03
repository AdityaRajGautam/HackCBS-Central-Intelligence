from flask import Flask, session, render_template, request
import os
import logging
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import cv2
import base64
import numpy as np
import face_recognition
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*")

users_data = {}
user_data = {}

# Load the model
logger.info("Model loaded successfully")


@app.route("/")
def index():
    user_id = session.get("user_id")
    if not user_id:
        session["user_id"] = random.randint(1, 100000)
    logger.info("Rendering index page")
    return render_template("home.html")


@socketio.on("connect")
def handle_connect():
    user_sid = session.get("user_id")
    join_room(user_sid)
    user_data[user_sid] = {"frames": []}
    print("Client connected started", user_sid)


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")
    user_sid = session.get("user_id")
    leave_room(user_sid)
    if user_sid in user_data:
        del user_data[user_sid]
        print(f"Client with SID {user_sid} disconnected")


@socketio.on("process_frame")
def process_frame(data):
    global user_data
    user_sid = session.get("user_id")
    print(f"Processing frame for client with SID {user_sid}")
    if user_sid in user_data:
        frame_data = data.get("frame", "")
        if frame_data:
            image_data = frame_data.split(",")[1]
            decoded_data = base64.b64decode(image_data)
            nparr = np.frombuffer(decoded_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))

            if len(faces) > 0:
                for (x, y, w, h) in faces:
                    name = recognize_face(
                        frame[y:y+h, x:x+w], data.get('location', None),data.get('time', ""), image_data)
                    # Emit to the specific client
                    emit("frame_processed", name, room=user_sid)


def recognize_face(face_image, location, time,image_data):
    rgb_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_image)

    if len(face_locations) == 0:
        return "No face detected!"  # No faces found

    face_encodings = face_recognition.face_encodings(rgb_image, face_locations)

    for face_encoding in face_encodings:
        for name, known_encoding in users_data.items():
            # Compare the detected face with known faces
            match = face_recognition.compare_faces(
                [known_encoding], face_encoding, tolerance=0.5)
            if match[0]:
                print(location)
                emit("reply", json.dumps({
                    'threatId': name,
                    'location': location,
                    'image': image_data,
                    'time': time,
                }), room='na52m')  # Emit to the specific client
                # do something if face matches
                return name
    # If no recognized faces are found, return "Unknown"
    return "Unkown"


@socketio.on("msg")
def msg(data):
    user_sid = request.args['user_id']
    join_room(user_sid)
    emit("reply", user_sid)  # Emit to the specific client


if __name__ == "__main__":
    image = face_recognition.load_image_file('nikhil.jpeg')
    image2 = face_recognition.load_image_file('dp.jpeg')
    face_encodingg = face_recognition.face_encodings(
        image)[0]  # Assuming there's only one face per image
    face_encodingg2 = face_recognition.face_encodings(
        image2)[0]  # Assuming there's only one face per image
    users_data['dp.jpg'] = face_encodingg2.tolist()
    users_data['nikhil.jpg'] = face_encodingg.tolist()
    host = os.getenv("HOST", "127.0.0.1")
    socketio.run(app, host="0.0.0.0", port=8000, log_output=True, debug=True)
