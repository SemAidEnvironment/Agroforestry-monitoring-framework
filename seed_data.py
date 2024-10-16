from app import app, db, Criteria

def seed_criteria():
    # Clear the Criteria table to prevent duplicates
    db.session.query(Criteria).delete()
    db.session.commit()

    # Add the new phase criterion
    phase_criterion = Criteria(
        name="phase",
        options="Project design,Baseline building,Mid term evaluation,End evaluation"
    )
    db.session.add(phase_criterion)

    # Add the new technical expertise criterion
    technical_expertise_criterion = Criteria(
        name="technical_expertise",
        options="low,medium,high"
    )
    db.session.add(technical_expertise_criterion)

    # Commit the new entries
    db.session.commit()

# Run the seeding within the app context
with app.app_context():
    seed_criteria()
