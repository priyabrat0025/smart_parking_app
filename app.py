from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from models import db, user , ParkingSpace , Booking , Feedback
from datetime import datetime, timedelta
from flask import render_template 
import os 


#initialize Flask app
app = Flask(__name__, instance_relative_config=True)

#set up SQLite database URI(auto-created if not found)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' +os.path.join(app.instance_path, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

#initialize the database with flask app
db.init_app(app)

@app.route('/')
def index():
    return "Smart parking app backend is Running!"


@app.route('/test_register' , methods=['GET'])
def test_register():
    return render_template('register.html')

#register a new user 
@app.route('/register', methods=['POST'])
def register():
    
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    new_user = user(
        name=data['name'],
        email=data['email'],
        password=data['password'],
        user_type=data['user_type']
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'user registered successfully' , 'user':{'id': new_user.id,
            'name': new_user.name,
            'email': new_user.email,
            'user_type': new_user.user_type
        }
    }), 201




@app.route('/users/<int:user_id>', methods=['GET'])
def get_user_details(user_id):
    user_obj = user.query.get(user_id)
    if user_obj:
        return jsonify({
            'id': user_obj.id,
            'name': user_obj.name,
            'email': user_obj.email,
            'user_type': user_obj.user_type
        }), 200
    return jsonify({'message': 'User not found'}), 404


#login user (simplified version)
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = user.query.filter_by(email=data['email'],password=data['password']).first()

    if user:
        return jsonify({'message': 'login successful', 'user_type':user.user_type})
    return jsonify({'message':'Invalid credentials'}), 401


#start Flask app
if __name__=='__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

from models import ParkingSpace  

# land owner adds a parking space

@app.route('/add_parking' , methods=['POST'])
def add_parking():
    data = request.get_json()

    new_space = ParkingSpace(
        location=data['location'],
        is_available=True,
        price_per_day = data['price_per_day'],
        owner_id=data['owner_id']
    )

    db.session.add(new_space)
    db.session.commit()

    return jsonify({'message': 'parking space added successfully'}),201


#customer searches for available parking in a location

@app.route('/search_parking' , methods=['GET'])
def search_parking():
    location = request.args.get('location') 
    if not location:
        return jsonify({'message': 'Location parameter is required'}), 400


    available_spaces = ParkingSpace.query.filter_by(
        location=location,
        is_available=True
    ).all()

    result =[]
    for space in available_spaces:
        result.append({
        'id': space.id,
        'location': space.location,
        'proce_per_day':space.price_per_day,
        'owner_id':space.owner_id
    })

    return jsonify({'available_spaces': result})

 #booking api
@app.route('/book_parking', methods=['POST'])
def book_parking():
    data = request.get_json()
    space = ParkingSpace.query.get(data['parking_space_id'])


    if not space or not space.is_available:
        return jsonify({'message': 'parking soace not available'}), 400

    start_date = datetime.strptime(data['start_date'], "%Y-%m-%d").date()
    end_date = start_date + timedelta(days=data['days'])
    
    #conflict check
    existing_bookings = Booking.query.filter_by(parking_space_id=space.id).all()
    for b in existing_bookings:
        if b.start_date and b.days:
            b_end = b.start_date + timedelta(days=b.days)
            if (start_date < b_end and end_date > b.start_date):
                return jsonify({'message': 'Conflict: This parking space is already booked for the selected dates.'}), 409

    try:
        start_date = datetime.strptime(data['start_date'], '%y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'Invalid date format. Use yy-mm-dd.'}), 400


    total = space.price_per_day * data['days']
    platform_cut = int(total *0.4)
    owner_cut = total - platform_cut
    end_date = start_date + timedelta(days=data['days'])

    booking = booking(
        customer_id = data['customer_id'],
        parking_space_id = data['parking_space_id'],
        days = data['days'],
        start_date = start_date,
        total_price = total,
        owner_earning = owner_cut,
        platform_earning = platform_cut
    )

    space.is_available = False
    db.session.add(booking)
    db.session.commit()

    return jsonify({'message': 'booking successful', 'total_price': total, 'platform_earning':platform_cut, 'owner_earning': owner_cut}), 201

#landowner: mark available/full

@app.route('/update_availability', methods=['POST'])
def update_availability():
    data = request.get_json()
    space = ParkingSpace.query.get(data['parking_space_id'])

    if not space:
        return jsonify({'message': 'space not found'}), 404
    
    space.is_available = data['is_available']
    db.session.commit()
    return jsonify({'message': 'availability updated'}),200


#get customer_bookings

@app.route('/customer_bookings/<int:customer_id>', methods=['GET'])
def get_customer_bookings(customer_id):
    bookings = booking.query.filter_by(customer_id=customer_id).all()
    result = []
    
    for booking in bookings:
        space = ParkingSpace.query.get(booking.parking_space_id)
        result.append({
            'location':space.location,
            'days': booking.days,
            'total_price': booking.total_price,
            'owner_earning': booking.owner_earning,
            'platform_earning': booking.platform_earning
        })
    return jsonify(result)

#get owner booking

@app.route('/owner_bookings/<int:owner_id>', methods=['GET'])
def get_owner_bookings(owner_id):
    spaces = ParkingSpace.query.filter_by(owner_id=owner_id).all()
    space_ids = [s.id for s in spaces]
    bookings = booking.query.filter(booking.parking_space_id.in_(space_ids)).all()

    result =[]
    for booking in bookings:
        space = ParkingSpace.query.get(booking.parking_space_id)
        customer = user.query.get(booking.customer_id)
        result.append({
            'location': space.locaton,
            'customer':customer.name,
            'days':booking.days,
            'total_price': booking.total_price
        })
        return jsonify(result)
#cancel booking 

@app.route('/cancel_booking/<int:booking_id>', methods=['PUT'])
def cancel_booking(booking_id):
    booking = booking.query.get(booking_id)
    if booking and booking.is_active:
        booking.is_active = False
        db.session.commit()
        return jsonify({'message': 'Booking cancelled successfully'}), 200
    return jsonify({'message': 'Booking not found or already cancelled'}), 404


with app.app_context():
    db.create_all()


#ml integration

from collections import Counter
from sqlalchemy import func


@app.route('/suggest_parking/<int:user_id>' , methods=['Get'])
def suggest_parking(user_id):

    user_bookings = Booking.query.filter_by(customer_id = user_id).all()

    if not user_bookings:
        all_bookings = Booking.query.all()
        location_counter = Counter()
        for b in user_bookings:
            space = ParkingSpace.query.get(b.parking_space_id)
            if space:
                location_counter[space.location]+=1
        top_locations = location_counter.most_common(10)
    else :
        location_counter = Counter()
        for b in user_bookings:
            space = ParkingSpace.query.get(b.parking_space_id)
            if space:
                location_counter[space.location] += 1

        top_locations = location_counter.most_common(10)

    # Fetch available parking spaces in those locations
    suggestions = []
    for location, _ in top_locations:
        spaces = ParkingSpace.query.filter_by(location=location, is_available=True).all()
        for space in spaces:
            suggestions.append({
                'id': space.id,
                'location': space.location,
                'price_per_day': space.price_per_day,
                'owner_id': space.owner_id
            })

    return jsonify({'suggestions': suggestions})
    return jsonify({'message': 'Route working!'})


    #for admin 
    #view all users

@app.route('/admin/users', methods = ['GET'])
def view_all_users():
    users = user.query.all()
    result = []
    for u in users:
     result.append({
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'user_type': u.user_type
        })
    return jsonify(result)

#view all parking space

@app.route('/admin/parkings' , methods=['GET'])
def view_all_parking_spaces():
    spaces = ParkingSpace.query.all()
    result = []
    for space in spaces:
        result.append({
            'id':space.id,
            'loaction': space.location,
            'is_available': space.is_available,
            'price_per_day':space.price_per_day,
            'owner_id': space.owner_id
        })
    return jsonify(result)

#view all bookings
@app.route('/admin/bookings', methods=['GET'])
def view_all_bookings():
    bookings = Booking.query.all()
    result = []
    for b in bookings:
        result.append({
              'id': b.id,
            'customer_id': b.customer_id,
            'parking_space_id': b.parking_space_id,
            'days': b.days,
            'total_price': b.total_price,
            'owner_earning': b.owner_earning,
            'platform_earning': b.platform_earning,
            'is_active': b.is_active
        })
    return jsonify(result)

#delete a user
@app.route('/admin/delete_user/<int:user_id>' , methods=['DELETE'])
def delete_user(user_id):
    u = user.query.get(user_id)
    if u:
        db.session.delete(u)
        db.session.commit()
        return jsonify({'message': 'user deleted successfully'})
    return jsonify({'message': 'user not found'}), 404


#admin earning summary
@app.route('/admin/earnings_summary', methods = ['GET'])
def earning_summary():
    bookings = Booking.query.all()

    total_platform_earning = sum([b.platform_earning for b in bookings if b.platform_earning])
    total_owner_earning = sum([b.owner_earning for b in bookings if b.owner_earning])
    total_bookings = len(bookings)

    # Optional: Location-wise breakdown
    location_summary = {}
    for booking in bookings:
        space = ParkingSpace.query.get(booking.parking_space_id)
        if space:
            loc = space.location
            if loc not in location_summary:
                location_summary[loc] = {
                    'total_bookings': 0,
                    'total_earning': 0
                }
            location_summary[loc]['total_bookings'] += 1
            location_summary[loc]['total_earning'] += booking.total_price

    return jsonify({
        'total_platform_earning': total_platform_earning,
        'total_owner_earning': total_owner_earning,
        'total_bookings': total_bookings,
        'location_summary': location_summary
    }), 200

#location wise booking

@app.route('/admin/location_stats' , methods = ['GET'])
def location_booking_stats():
    stats = db.session.query(
        ParkingSpace.location,
        db.func.count(Booking.id).label('total_bookings')
    ).join(Booking, ParkingSpace.id == Booking.parking_space_id)\
     .group_by(ParkingSpace.location)\
     .all()

#feedback 

@app.route('/submit_feedback', methods = ['POST'])
def submit_feedback():
    data = request.get_json()
    feedback = Feedback(
        user_id = data['user_id'],
        parking_space_id = data['parking_space_id'],
        rating = data['rating'],
        comment = data.get('comment', '')
    )
    db.session.add(feedback)
    db.session.commit()
    return jsonify({'message':'feedback submitted successfully'}), 201

#view feedback
@app.route('/feedback/<int:parking_space_id>' , methods=['GET'])
def view_feedback(parking_space_id):
    feedbacks = Feedback.query.filter_by(parking_space_id=parking_space_id).all()
    result = []
    for f in feedbacks:
        user_obj = user.query.get(f.user_id)
        result.append({
            'user': user_obj.name if user_obj else "unkown",
            'rating': f.rating,
            'commwnt':f.comment,
            'timestamp': f.timestamp.strftime('%y-%m-%d %H:%M:%S')
        })
    return jsonify(result)

#top-rated suggestions

def suggest_top_rates():
    #fetch all spaces
    spaces = ParkingSpace.query.filter_by(is_available=True).all()
    rated_spaces = []

    for space in spaces:
        feedbacks = Feedback.query.filter_by(parking_space_id = space.id).all()
        if feedbacks:
            avg_rating = sum([f.rating for f in feedbacks]) / len(feedbacks)
            rated_spaces.append((space, avg_rating))

    # sort by rating descending
    rated_spaces.sort(key = lambda x: x[1], reverse=True)

    suggestions = []
    for space, rating in rated_spaces[:10]:
        suggestions.append({
            'id': space.id,
            'location': space.location,
            'price_per_day': space.price_per_day,
            'owner_id': space.owner_id,
            'average_rating': round(rating, 2)
        })
    return jsonify({'top_rated_spaces': suggestions}), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Creates tables in the database if not already present
    app.run(debug=True)
