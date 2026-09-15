import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

from ebay_client import EbayAPIError, EbayClient

load_dotenv()

app = Flask(__name__)
CORS(app)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ebay_sales.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class SoldItem(db.Model):
    __tablename__ = "sold_items"

    id = db.Column(db.Integer, primary_key=True)
    ebay_item_id = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(500), nullable=False)
    sold_price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="USD")
    sold_date = db.Column(db.String(50), nullable=False)
    ebay_link = db.Column(db.String(500), nullable=False)
    seller = db.Column(db.String(100), default="")
    condition = db.Column(db.String(100), default="")
    listing_type = db.Column(db.String(50), default="")
    payment_received = db.Column(db.Boolean, default=False, nullable=False)
    item_received = db.Column(db.Boolean, default=False, nullable=False)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "ebay_item_id": self.ebay_item_id,
            "title": self.title,
            "sold_price": self.sold_price,
            "currency": self.currency,
            "sold_date": self.sold_date,
            "ebay_link": self.ebay_link,
            "seller": self.seller,
            "condition": self.condition,
            "listing_type": self.listing_type,
            "payment_received": self.payment_received,
            "item_received": self.item_received,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }


with app.app_context():
    db.create_all()


def get_ebay_client():
    app_id = os.getenv("EBAY_APP_ID", "").strip()
    if not app_id:
        raise ValueError("EBAY_APP_ID is not set. Add it to your .env file.")
    env = os.getenv("EBAY_ENV", "production")
    return EbayClient(app_id, env)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json(force=True)
    seller = (data.get("seller") or "").strip()
    date_from = (data.get("date_from") or "").strip()
    date_to = (data.get("date_to") or "").strip()

    if not seller:
        return jsonify({"error": "Seller username is required"}), 400

    try:
        client = get_ebay_client()
        items = client.find_sold_items(seller, date_from or None, date_to or None)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except EbayAPIError as e:
        return jsonify({"error": f"eBay API error: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Search failed: {e}"}), 500

    existing_ids = {
        row.ebay_item_id
        for row in db.session.execute(db.select(SoldItem.ebay_item_id)).scalars()
    }
    for item in items:
        item["already_saved"] = item["ebay_item_id"] in existing_ids

    return jsonify({"items": items, "total": len(items)})


@app.route("/api/items", methods=["GET"])
def get_items():
    seller_filter = request.args.get("seller", "").strip()
    query = db.select(SoldItem).order_by(SoldItem.sold_date.desc())
    if seller_filter:
        query = query.where(SoldItem.seller == seller_filter)
    items = db.session.execute(query).scalars().all()
    return jsonify({"items": [i.to_dict() for i in items]})


@app.route("/api/items", methods=["POST"])
def save_items():
    data = request.get_json(force=True)
    items_data = data.get("items", [])
    if not items_data:
        return jsonify({"error": "No items provided"}), 400

    saved, skipped = 0, 0
    for item_data in items_data:
        exists = db.session.execute(
            db.select(SoldItem).where(SoldItem.ebay_item_id == item_data["ebay_item_id"])
        ).scalar_one_or_none()
        if exists:
            skipped += 1
            continue
        item = SoldItem(
            ebay_item_id=item_data["ebay_item_id"],
            title=item_data["title"],
            sold_price=item_data["sold_price"],
            currency=item_data.get("currency", "USD"),
            sold_date=item_data["sold_date"],
            ebay_link=item_data["ebay_link"],
            seller=item_data.get("seller", ""),
            condition=item_data.get("condition", ""),
            listing_type=item_data.get("listing_type", ""),
        )
        db.session.add(item)
        saved += 1

    db.session.commit()
    return jsonify({"saved": saved, "skipped": skipped})


@app.route("/api/items/<int:item_id>", methods=["PATCH"])
def update_item(item_id):
    item = db.session.get(SoldItem, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    data = request.get_json(force=True)
    if "payment_received" in data:
        item.payment_received = bool(data["payment_received"])
    if "item_received" in data:
        item.item_received = bool(data["item_received"])
    if "notes" in data:
        item.notes = str(data["notes"])

    db.session.commit()
    return jsonify(item.to_dict())


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    item = db.session.get(SoldItem, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/stats", methods=["GET"])
def stats():
    all_items = db.session.execute(db.select(SoldItem)).scalars().all()
    total_revenue = sum(i.sold_price for i in all_items)
    payment_pending = [i for i in all_items if not i.payment_received]
    items_pending = [i for i in all_items if not i.item_received]
    return jsonify({
        "total_items": len(all_items),
        "total_revenue": round(total_revenue, 2),
        "payment_pending_count": len(payment_pending),
        "payment_pending_value": round(sum(i.sold_price for i in payment_pending), 2),
        "items_pending_count": len(items_pending),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
