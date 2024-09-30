from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///items.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define the Item model
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

# Create the database and tables
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')  # Serve the HTML page

@app.route('/items', methods=['GET'])
def get_items():
    items = Item.query.all()
    return jsonify([{'id': item.id, 'name': item.name} for item in items])

@app.route('/items', methods=['POST'])
def add_item():
    item_name = request.json.get('item')
    if item_name:
        new_item = Item(name=item_name)
        db.session.add(new_item)
        db.session.commit()
        return jsonify({'message': 'Item added successfully!'}), 201
    return jsonify({'message': 'No item provided!'}), 400

@app.route('/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    item = Item.query.get(item_id)
    if item:
        db.session.delete(item)
        db.session.commit()
        return jsonify({'message': f'Item "{item.name}" deleted successfully!'})
    return jsonify({'message': 'Item not found!'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)  # Make sure it's accessible
