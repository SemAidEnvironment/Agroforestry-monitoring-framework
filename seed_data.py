from app import app, db, Criteria
import json

def seed_criteria():
    # Clear the Criteria table to prevent duplicates
    db.session.query(Criteria).delete()
    db.session.commit()

    # Load criteria from JSON file
    with open('static/data/criteria.json', 'r') as file:
        criteria_list = json.load(file)

    # Add criteria dynamically
    for criterion in criteria_list:
        new_criterion = Criteria(
            name=criterion['name'],
            options=criterion['options']
        )
        db.session.add(new_criterion)

    # Commit the new entries
    db.session.commit()


# Run the seeding within the app context
with app.app_context():
    seed_criteria()
