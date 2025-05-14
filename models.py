from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class user(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True , nullable=False)
    password = db.Column(db.String(100), nullable=False)
    user_type = db.Column(db.String(20))

#parkingspace model: listed by landowners

class ParkingSpace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(200), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    price_per_day = db.Column(db.Float, nullable=False)

    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    owner = db.relationship('user', backref='parking_spaces')

class Booking(db.Model):
  id =db.Column(db.Integer , primary_key=True)
  customer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
  parking_space_id = db.Column(db.Integer, db.ForeignKey('parking_space.id'))
  days = db.Column(db.Integer)
  start_date = db.Column(db.Date)
  total_price = db.Column(db.Integer)
  owner_earning = db.Column(db.Integer)
  platform_earning = db.Column(db.Integer)
  is_active = db.Column(db.Boolean, default=True)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    parking_space_id = db.Column(db.Integer, db.ForeignKey('parking_space.id'))
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default = datetime.utcnow)