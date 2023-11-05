from flask import Flask, session, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import json
import cv2
import os
import base64
import numpy as np
import face_recognition
from flask_cors import CORS

# load cv2 modal
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
media_folder_path = 'media'
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*")

users_data = {}
user_data = {}


@app.route("/")
def index():
    user_id = session.get("user_id")
    if not user_id:
        session["user_id"] = random.randint(1, 100000)
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


# Function to save an image with a specific filename format
def save_image(image, filename):
    print(image, filename)
    image_path = os.path.join(media_folder_path, filename)
    image.save(image_path)


def isAuthorized():
    uid = request.args.get('user_id')
    if uid == "szg0IndRBkZVCFDfUqYh73oOoG72":
        return True
    return jsonify({"message": "not authorized!"})


@app.route('/create_user', methods=['POST'])
def create_user():
    isAuth = isAuthorized()
    if isAuth == True:
        pass
    else:
        return isAuth
    data = request.form

    user_id = data.get('id')
    user_name = data.get('name')
    user_image = request.files['image']

    if user_id is None or user_name is None or user_image is None:
        return jsonify({"error": "Incomplete data"}), 400

    # Create a unique filename based on user ID and name
    image_filename = f"{user_id}_{user_name}.jpeg"

    # Save the image to the media folder
    save_image(user_image, image_filename)

    # Perform face recognition and store the face encoding in the users_data dictionary
    image = face_recognition.load_image_file(
        os.path.join(media_folder_path, image_filename))
    face_encodings = face_recognition.face_encodings(image)

    if face_encodings:
        # Assuming there's only one face per image
        face_encoding = face_encodings[0]
        users_data[user_id] = {
            'image_filename': filename,
            'encodings': face_encoding.tolist()
        }

    return jsonify({"message": "User created successfully"})


@app.route('/delete_user/<user_id>', methods=['GET'])
def delete_user(user_id):
    isAuth = isAuthorized()
    if isAuth == True:
        pass
    else:
        return isAuth
    if user_id in users_data:
        # Remove the user's image file from the media folder
        image_filename = users_data[user_id]['image_filename']
        image_path = os.path.join(media_folder_path, image_filename)
        os.remove(image_path)

        # Remove the user's data from the users_data dictionary
        del users_data[user_id]

        return jsonify({"message": f"User with ID {user_id} has been deleted"})
    else:
        return jsonify({"error": f"User with ID {user_id} not found"}), 404


@app.route('/user_ids', methods=['GET'])
def get_user_ids():
    isAuth = isAuthorized()
    if isAuth == True:
        pass
    else:
        return isAuth
    user_ids = list(users_data.keys())
    return jsonify(user_ids)


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
                    recognize_face(
                        frame[y:y+h, x:x+w], data.get('location', None), data.get('time', ""), image_data)
                    # Emit to the specific client
                    emit("frame_processed", "sending frames..", room=user_sid)


def recognize_face(face_image, location, time, image_data):
    rgb_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_image)

    if len(face_locations) == 0:
        return "No face detected!"  # No faces found

    face_encodings = face_recognition.face_encodings(rgb_image, face_locations)

    for face_encoding in face_encodings:
        for name, known_encoding in users_data.items():
            # Compare the detected face with known faces
            match = face_recognition.compare_faces(
                [known_encoding['encodings']], face_encoding, tolerance=0.5)
            if match[0]:
                emit("frame_processed_controller", json.dumps({
                    'threatId': name,
                    'location': location,
                    'image': image_data,
                    'time': time,
                }), room='szg0IndRBkZVCFDfUqYh73oOoG72')  # Emit to the specific client

                # do something if face matches
                print(f"target {name} is detected at location {location}")
                return name
    # If no recognized faces are found, return "Unknown"
    return "Unkown"


@socketio.on("connect_control_room")
def connect_control_room(data):
    user_sid = request.args['user_id']
    join_room(user_sid)
    emit("connected", user_sid)  # Emit to the specific client


if __name__ == "__main__":
    # List all files in the media folder
    for filename in os.listdir(media_folder_path):
        if filename.endswith(".jpeg"):
            image_path = os.path.join(media_folder_path, filename)
            image = face_recognition.load_image_file(image_path)
            face_encodings = face_recognition.face_encodings(image)

            if face_encodings:
                # Assuming there's only one face per image
                face_encoding = face_encodings[0]
                users_data[filename.split('_')[0]] = {
                    'image_filename': filename,
                    'encodings': face_encoding.tolist()
                }

    host = os.getenv("HOST", "127.0.0.1")
    socketio.run(app, host="0.0.0.0", port=8000, log_output=True, debug=True)
