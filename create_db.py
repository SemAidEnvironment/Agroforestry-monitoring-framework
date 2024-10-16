from app import db, app  # Import both the database instance and Flask app

# Create an application context
with app.app_context():
    db.create_all()
    print("Database tables created successfully!")
