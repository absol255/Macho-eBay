from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True)

    username = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    macho_bucks = db.Column(
        db.Numeric,
        default=0,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
    )

    bank_account_number = db.Column(
        db.BigInteger,
        default=999,
    )

    products = db.relationship("Product", backref="seller", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "macho_bucks": self.macho_bucks,
            "bank_account_number": self.bank_account_number,
        }


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.BigInteger, primary_key=True)

    seller_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    name = db.Column(db.String(128), nullable=False)

    image_data = db.Column(db.Text, nullable=False)

    quantity = db.Column(db.Integer, nullable=False)

    price = db.Column(db.Numeric, nullable=False)

    status = db.Column(
        db.String(16),
        default="pending",
        nullable=False,
        index=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
    )

    def to_dict(self, include_image=True):
        data = {
            "id": self.id,
            "seller_id": self.seller_id,
            "seller_username": self.seller.username if self.seller else None,
            "name": self.name,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_image:
            data["image_data"] = self.image_data
        return data


class Admin(UserMixin, db.Model):
    __tablename__ = "admins"

    id = db.Column(db.BigInteger, primary_key=True)

    username = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
    )

    password_hash = db.Column(
        db.String(256),
        nullable=False,
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
