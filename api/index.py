from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime
import bcrypt
import os

app = Flask(__name__)
CORS(app)  # Allow frontend to call API

# --- MongoDB Connection (Vercel environment) ---
# You must set MONGODB_URI in Vercel Environment Variables
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGODB_URI)
db = client['exampro_db']

# Collections
users_collection = db['users']
exams_collection = db['exams']
tests_collection = db['tests']
results_collection = db['results']
questions_collection = db['questions']

# -------------------- UTILITY --------------------
def serialize_doc(doc):
    if doc:
        doc['_id'] = str(doc['_id'])
    return doc

def create_sample_data():
    if exams_collection.count_documents({}) == 0:
        sample_test = {
            'name': 'Sample Hindi Grammar Test',
            'subject': 'हिंदी व्याकरण',
            'category': 'विलोम / पर्यायवाची',
            'difficulty': 'medium',
            'duration': 10,
            'totalMarks': 5,
            'passingMarks': 3,
            'posMarks': 1,
            'negMarks': 0.25,
            'published': True,
            'createdAt': datetime.datetime.utcnow().isoformat(),
            'questions': [
                {
                    'id': 'q1', 'question': 'निम्नलिखित में से किस विकल्प में सभी विलोम-युग्म सही हैं?',
                    'optionA': 'साधम्यं - वैधम्यं', 'optionB': 'निध - वंद्य', 'optionC': 'अद्यतन - अनद्यतन', 'optionD': 'नैसर्गिक - कृतिम',
                    'correctAnswer': 'C', 'solution': 'विकल्प (3) में अद्यतन का विलोम अनद्यतन है।'
                },
                {
                    'id': 'q2', 'question': 'निम्नलिखित में से विलोम-युग्म कौन-सा है?',
                    'optionA': 'अपदस्थ - पदच्युत', 'optionB': 'निर्भय - अभय', 'optionC': 'प्रसार - संकोच', 'optionD': 'मोक्ष - युक्त',
                    'correctAnswer': 'C', 'solution': 'प्रसार का अर्थ फैलाव और संकोच का अर्थ सिकुड़न है।'
                }
            ]
        }
        test_id = tests_collection.insert_one(sample_test).inserted_id
        
        exam = {
            'name': 'General Exams',
            'isVisible': True,
            'testTypes': [{
                'name': 'General Tests',
                'isVisible': True,
                'tests': [str(test_id)]
            }]
        }
        exams_collection.insert_one(exam)

# -------------------- AUTH ROUTES --------------------
@app.route('/api/register/student', methods=['POST'])
def register_student():
    data = request.json
    if users_collection.find_one({'email': data['email'], 'role': 'student'}):
        return jsonify({'error': 'Email already registered'}), 400

    hashed = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
    student = {
        'name': data['name'], 'mobile': data['mobile'], 'email': data['email'],
        'password': hashed.decode('utf-8'), 'role': 'student', 'banned': False,
        'deviceId': data.get('deviceId', ''), 'registeredAt': datetime.datetime.utcnow().isoformat()
    }
    result = users_collection.insert_one(student)
    return jsonify({'id': str(result.inserted_id), 'message': 'Registered successfully'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = users_collection.find_one({'email': data['email'], 'role': data['role']})
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if bcrypt.checkpw(data['password'].encode('utf-8'), user['password'].encode('utf-8')):
        user_data = serialize_doc(user)
        user_data.pop('password')
        return jsonify({'user': user_data, 'userType': user_data['role']}), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

# -------------------- EXAMS & TESTS --------------------
@app.route('/api/exams', methods=['GET'])
def get_exams():
    create_sample_data() # Auto-create sample data if empty
    exams = list(exams_collection.find({}))
    for exam in exams:
        serialize_doc(exam)
    return jsonify(exams)

@app.route('/api/tests/<test_id>', methods=['GET'])
def get_test(test_id):
    test = tests_collection.find_one({'_id': ObjectId(test_id)})
    if not test: return jsonify({'error': 'Test not found'}), 404
    return jsonify(serialize_doc(test))

@app.route('/api/tests', methods=['POST'])
def create_test():
    data = request.json
    test_doc = {
        'name': data['name'], 'examId': data.get('examId'), 'testTypeId': data.get('testTypeId'),
        'subject': data.get('subject'), 'category': data.get('category'), 'difficulty': data.get('difficulty'),
        'duration': int(data.get('duration', 60)), 'totalMarks': int(data.get('totalMarks', 100)),
        'passingMarks': int(data.get('passingMarks', 33)), 'posMarks': float(data.get('posMarks', 1)),
        'negMarks': float(data.get('negMarks', 0.25)), 'startDate': data.get('startDate'),
        'endDate': data.get('endDate'), 'accessCode': data.get('accessCode'), 'instructions': data.get('instructions'),
        'questions': data['questions'], 'published': False, 'createdAt': datetime.datetime.utcnow().isoformat()
    }
    result = tests_collection.insert_one(test_doc)
    return jsonify({'id': str(result.inserted_id), 'message': 'Test created'}), 201

@app.route('/api/tests/<test_id>/publish', methods=['PUT'])
def toggle_publish(test_id):
    data = request.json
    tests_collection.update_one({'_id': ObjectId(test_id)}, {'$set': {'published': data.get('published', False)}})
    return jsonify({'message': 'Status updated'})

# -------------------- RESULTS --------------------
@app.route('/api/results', methods=['POST'])
def submit_result():
    data = request.json
    result_doc = {
        'testId': data['testId'], 'studentId': data['studentId'], 'studentName': data['studentName'],
        'score': data['score'], 'totalMarks': data['totalMarks'], 'percentage': data['percentage'],
        'passed': data['passed'], 'correct': data['correct'], 'wrong': data['wrong'],
        'skipped': data['skipped'], 'totalQuestions': data['totalQuestions'], 'timeUsed': data['timeUsed'],
        'questionResults': data['questionResults'], 'violations': data['violations'],
        'completedAt': datetime.datetime.utcnow().isoformat()
    }
    result = results_collection.insert_one(result_doc)
    return jsonify({'id': str(result.inserted_id), 'message': 'Result saved'}), 201

@app.route('/api/results/student/<student_id>', methods=['GET'])
def get_student_results(student_id):
    results = list(results_collection.find({'studentId': student_id}).sort('completedAt', -1))
    for r in results: serialize_doc(r)
    return jsonify(results)

# -------------------- ADMIN ROUTES --------------------
@app.route('/api/students', methods=['GET'])
def get_students():
    students = list(users_collection.find({'role': 'student'}))
    for s in students: serialize_doc(s); s.pop('password')
    return jsonify(students)

@app.route('/api/students/<student_id>', methods=['PUT'])
def update_student(student_id):
    data = request.json
    update_data = {}
    if 'name' in data: update_data['name'] = data['name']
    if 'mobile' in data: update_data['mobile'] = data['mobile']
    if 'email' in data: update_data['email'] = data['email']
    if 'password' in data: 
        update_data['password'] = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    users_collection.update_one({'_id': ObjectId(student_id)}, {'$set': update_data})
    return jsonify({'message': 'Updated'})

# Vercel expects a handler function named 'app'
# The Flask app is already called 'app', we just need to export it.
# This file will be imported by Vercel.
