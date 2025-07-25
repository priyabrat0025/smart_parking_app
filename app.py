from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from collections import Counter

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "your_secret_key"  # put something random & secret here

# MongoDB setup
client = MongoClient("mongodb://localhost:27017/")
db = client["smart_parking"]
users = db["users"]
spaces = db["parking_spaces"]
bookings = db["bookings"]
feedbacks = db["feedbacks"]


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET'])
def show_register():
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    user_email = session.get("user_email")
    if not user_email:
        return redirect(url_for('login'))

    user = users.find_one({"email": user_email})
    if not user:
        return "User not found", 404

    user_type = user.get("user_type")
    user_name = user.get("name")
    user_id = str(user["_id"])

    available_spaces = spaces.count_documents({"is_available": True})

    bookings_count = 0
    total_price = 0
    owner_earnings = 0
    platform_earnings = 0

    if user_type == "customer":
        customer_bookings = list(bookings.find({"customer_id": user_id}))
        bookings_count = len(customer_bookings)
        total_price = sum(b.get("total_price", 0) for b in customer_bookings)

    elif user_type == "owner":
        owner_spaces = list(spaces.find({"owner_id": user_id}))
        space_ids = [str(s["_id"]) for s in owner_spaces]
        owner_bookings = list(bookings.find({"parking_space_id": {"$in": space_ids}}))
        bookings_count = len(owner_bookings)
        owner_earnings = sum(b.get("owner_earning", 0) for b in owner_bookings)

    elif user_type == "admin":
        all_bookings = list(bookings.find())
        bookings_count = len(all_bookings)
        owner_earnings = sum(b.get("owner_earning", 0) for b in all_bookings)
        platform_earnings = sum(b.get("platform_earning", 0) for b in all_bookings)

    return render_template(
        "dashbord.html",
        user_name=user_name,
        user_type=user_type,
        available_spaces=available_spaces,
        bookings_count=bookings_count,
        total_price=total_price,
        owner_earnings=owner_earnings,
        platform_earnings=platform_earnings
    )

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() if request.is_json else request.form
    if users.find_one({"email": data['email']}):
        return jsonify({'message': 'User already exists'}), 409
    user_data = {
        "name": data['name'],
        "email": data['email'],
        "password": data['password'],
        "user_type": data['user_type']
    }
    result = users.insert_one(user_data)
    user_data['_id'] = str(result.inserted_id)
    return jsonify({'message': 'user registered successfully', 'user': user_data}), 201

from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from pymongo import MongoClient

app.secret_key = 'your_secret_key'  # Required for session handling

# existing MongoDB setup
client = MongoClient("mongodb://localhost:27017/")
db = client["smart_parking"]
users = db["users"]
# ... rest unchanged ...

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form['email']
    password = request.form['password']

    u = users.find_one({"email": email, "password": password})
    if u:
        session['user_email'] = u['email']
        return redirect(url_for('dashboard'))
    else:
        return render_template('login.html', error="Invalid credentials.")


@app.route('/add_parking', methods=['POST'])
def add_parking():
    data = request.get_json()
    new_space = {
        "location": data['location'],
        "is_available": True,
        "price_per_day": data['price_per_day'],
        "owner_id": data['owner_id']
    }
    spaces.insert_one(new_space)
    return jsonify({'message': 'parking space added successfully'}), 201

@app.route('/search_parking', methods=['GET'])
def search_parking():
    location = request.args.get('location')
    if not location:
        return jsonify({'message': 'Location parameter is required'}), 400

    # Use case-insensitive regex match to support flexible search
    query = {
        "location": {"$regex": location, "$options": "i"},
        "is_available": True
    }

    available = list(spaces.find(query))
    for s in available:
        s['_id'] = str(s['_id'])
    return jsonify({'available_spaces': available})
@app.route('/book_parking', methods=['POST'])
def book_parking():
    data = request.get_json()
    space = spaces.find_one({"_id": ObjectId(data['parking_space_id'])})
    if not space or not space['is_available']:
        return jsonify({'message': 'parking space not available'}), 400
    start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
    end_date = start_date + timedelta(days=data['days'])
    existing = bookings.find({"parking_space_id": data['parking_space_id']})
    for b in existing:
        b_start = b['start_date']
        b_end = b_start + timedelta(days=b['days'])
        if start_date < b_end and end_date > b_start:
            return jsonify({'message': 'Conflict: Already booked'}), 409
    total = space['price_per_day'] * data['days']
    owner_cut = total * 0.6
    booking = {
        "customer_id": data['customer_id'],
        "parking_space_id": data['parking_space_id'],
        "days": data['days'],
        "start_date": start_date,
        "total_price": total,
        "owner_earning": owner_cut,
        "platform_earning": total - owner_cut,
        "is_active": True
    }
    bookings.insert_one(booking)
    spaces.update_one({"_id": space['_id']}, {"$set": {"is_available": False}})
    return jsonify({'message': 'booking successful'}), 201

@app.route('/update_availability', methods=['POST'])
def update_availability():
    data = request.get_json()
    result = spaces.update_one({"_id": ObjectId(data['parking_space_id'])}, {"$set": {"is_available": data['is_available']}})
    if result.modified_count:
        return jsonify({'message': 'availability updated'})
    return jsonify({'message': 'space not found'}), 404

@app.route('/customer_bookings/<customer_id>', methods=['GET'])
def customer_bookings_view(customer_id):
    user_bookings = list(bookings.find({"customer_id": customer_id}))
    for b in user_bookings:
        b['_id'] = str(b['_id'])
        b['start_date'] = b['start_date'].strftime('%Y-%m-%d')
    return jsonify(user_bookings)

@app.route('/owner_bookings/<owner_id>', methods=['GET'])
def owner_bookings_view(owner_id):
    owner_spaces = list(spaces.find({"owner_id": owner_id}))
    space_ids = [str(s['_id']) for s in owner_spaces]
    owner_bookings = list(bookings.find({"parking_space_id": {"$in": space_ids}}))
    for b in owner_bookings:
        b['_id'] = str(b['_id'])
    return jsonify(owner_bookings)

@app.route('/cancel_booking/<booking_id>', methods=['PUT'])
def cancel_booking(booking_id):
    updated = bookings.update_one({"_id": ObjectId(booking_id)}, {"$set": {"is_active": False}})
    if updated.modified_count:
        return jsonify({'message': 'Booking cancelled'})
    return jsonify({'message': 'Not found or already cancelled'}), 404

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    data = request.get_json()
    data['timestamp'] = datetime.now()
    feedbacks.insert_one(data)
    return jsonify({'message': 'feedback submitted successfully'}), 201

@app.route('/feedback/<parking_space_id>', methods=['GET'])
def view_feedback(parking_space_id):
    fb_list = list(feedbacks.find({"parking_space_id": parking_space_id}))
    for f in fb_list:
        f['_id'] = str(f['_id'])
        f['timestamp'] = f['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(fb_list)

@app.route('/admin/users', methods=['GET'])
def admin_users():
    all_users = list(users.find())
    for u in all_users:
        u['_id'] = str(u['_id'])
    return jsonify(all_users)

@app.route('/admin/bookings', methods=['GET'])
def admin_bookings():
    all_bookings = list(bookings.find())
    for b in all_bookings:
        b['_id'] = str(b['_id'])
        b['start_date'] = b['start_date'].strftime('%Y-%m-%d')
    return jsonify(all_bookings)

@app.route('/admin/parkings', methods=['GET'])
def admin_parkings():
    all_spaces = list(spaces.find())
    for s in all_spaces:
        s['_id'] = str(s['_id'])
    return jsonify(all_spaces)

@app.route('/admin/earnings_summary', methods=['GET'])
def earnings_summary():
    all = list(bookings.find())
    summary = {
        'total_platform_earning': sum(b['platform_earning'] for b in all),
        'total_owner_earning': sum(b['owner_earning'] for b in all),
        'total_bookings': len(all)
    }
    return jsonify(summary)

@app.route('/suggest_parking/<customer_id>', methods=['GET'])
def suggest_parking(customer_id):
    all_book = list(bookings.find({"customer_id": customer_id}))
    loc_counter = Counter()

    for b in all_book:
        space = spaces.find_one({"_id": ObjectId(b['parking_space_id'])})
        if space:
            loc_counter[space['location']] += 1

    result = []

    # If customer has no history, return any available space without conflict
    if not loc_counter:
        available_spaces = list(spaces.find({"is_available": True}))
        for s in available_spaces:
            s_id = str(s['_id'])
            bookings_for_space = list(bookings.find({"parking_space_id": s_id}))
            has_future_booking = any(
                (datetime.now() < b['start_date'] + timedelta(days=b['days'])) and b.get("is_active", True)
                for b in bookings_for_space
            )
            if not has_future_booking:
                s['_id'] = s_id
                result.append(s)
    else:
        top = [loc for loc, _ in loc_counter.most_common(5)]
        for loc in top:
            found_spaces = list(spaces.find({"location": loc, "is_available": True}))
            for s in found_spaces:
                s_id = str(s['_id'])
                bookings_for_space = list(bookings.find({"parking_space_id": s_id}))
                has_future_booking = any(
                    (datetime.now() < b['start_date'] + timedelta(days=b['days'])) and b.get("is_active", True)
                    for b in bookings_for_space
                )
                if not has_future_booking:
                    s['_id'] = s_id
                    result.append(s)

    return jsonify({'suggestions': result})

@app.route('/debug_users')
def debug_users():
    data = list(users.find())
    for u in data:
        u['_id'] = str(u['_id'])
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)


