from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pandas as pd
import json

def check_missing_criteria_answers(project):
    # Get all required criteria
    required_criteria_ids = {c.id for c in Criteria.query.all()}

    # Get all criteria ids that have been answered for the project
    answered_criteria_ids = {pc.criteria_id for pc in project.project_criteria}

    # Determine if any criteria are missing
    missing_criteria_ids = required_criteria_ids - answered_criteria_ids
    return len(missing_criteria_ids) > 0

# Flask app initialization
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    projects = db.relationship('Project', backref='owner', lazy=True)

# Project model
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_criteria = db.relationship('ProjectCriteria', backref='project', cascade="all, delete", lazy=True)
    techniques = db.relationship('SelectedTechnique', backref='project', cascade="all, delete", lazy=True)

class Criteria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    options=db.Column(db.String(500))

class ProjectCriteria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    criteria_id = db.Column(db.Integer, db.ForeignKey('criteria.id'), nullable=False)
    answer = db.Column(db.String(50))
    # Establishing relationships to Project and Criteria models
    criteria = db.relationship('Criteria', backref='project_criteria')

# SelectedTechnique model
class SelectedTechnique(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    technique_name = db.Column(db.String(100), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    image_filename = db.Column(db.String(100), nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('account'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html')


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('account'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not password:
            flash('Password cannot be empty', 'danger')
            return redirect(url_for('register'))
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You can now log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


# Account page route
@app.route("/account")
@login_required
def account():
    projects = Project.query.filter_by(user_id=current_user.id).all()
    for project in projects:
        if check_missing_criteria_answers(project):
            flash("One of your projects requires updated criteria answers. Please answer the new questions.", "warning")
            return redirect(url_for('questions', project_id=project.id))

    project_details = []
    for project in projects:
        criteria_answers = {pc.criteria.name: pc.answer for pc in project.project_criteria}
        techniques = [technique.technique_name for technique in project.techniques]
        project_details.append({
            'project': project,
            'criteria_answers': criteria_answers,
            'techniques': techniques
        })
    return render_template('account.html', projects=projects, project_details=project_details)





# Unified create and edit project route
@app.route("/questions", methods=["GET", "POST"])
@login_required
def questions():
    project_id = request.args.get('project_id')
    project = db.session.get(Project, project_id) if project_id else None  # Updated to use db.session.get()

    # Convert Criteria model instances to dictionaries with split options
    criteria = [
        {
            "id": criterion.id,
            "name": criterion.name,
            "options": criterion.options.split(",")
        }
        for criterion in Criteria.query.all()
    ]

    # Load subsections from reporting_area.json
    with open('static/data/reporting_area.json', 'r') as json_file:
        reporting_areas = json.load(json_file)["reporting_areas"]

    if request.method == "POST":
        errors = []

        if not project:
            project_name = request.form.get("project_name")
            project = Project(name=project_name, owner=current_user)
            db.session.add(project)
            db.session.commit()

        # Save or update criteria answers
        selected_areas = request.form.getlist("criteria_reporting_area")
        selected_subsections = request.form.getlist("criteria_subsections")

        # Validation: Ensure at least one reporting area is selected
        if not selected_areas:
            errors.append("Please select at least one reporting area.")

        # Validation: Ensure at least one subsection is selected per selected reporting area
        for area in reporting_areas:
            if area["name"] in selected_areas:
                area_subsections = [sub["name"] for sub in area.get("subsections", [])]
                if not any(sub in selected_subsections for sub in area_subsections):
                    errors.append(f"Please select at least one subsection for '{area['name']}'.")

        if errors:
            for error in errors:
                flash(error, "danger")  # Ensure "danger" matches the template's CSS class
            return render_template(
                "questions.html",
                project=project,
                criteria=criteria,
                reporting_areas=reporting_areas,
                project_criteria_answers={
                    pc.criteria.name: pc.answer.split(",")
                    if pc.criteria.name in ["reporting_area", "subsections"]
                    else pc.answer
                    for pc in project.project_criteria
                }
                if project
                else {},
            )

        # Save or update criteria answers
        for criterion in criteria:
            if criterion["name"] == "reporting_area":
                selected_areas = request.form.getlist(f"criteria_{criterion['name']}")
                answer = ",".join(selected_areas)
            elif criterion["name"] == "subsections":
                selected_subsections = request.form.getlist(f"criteria_{criterion['name']}")
                answer = ",".join(selected_subsections)
            else:
                answer = request.form.get(f"criteria_{criterion['name']}")

            if answer:
                project_criteria = ProjectCriteria.query.filter_by(
                    project_id=project.id, criteria_id=criterion["id"]
                ).first()

                if project_criteria:
                    project_criteria.answer = answer
                else:
                    new_project_criteria = ProjectCriteria(
                        project_id=project.id, criteria_id=criterion["id"], answer=answer
                    )
                    db.session.add(new_project_criteria)

        db.session.commit()
        return redirect(url_for("longlist", project_id=project.id))

    # Prepare existing answers for display
    project_criteria_answers = {
        pc.criteria.name: pc.answer.split(",") if pc.criteria.name in ["reporting_area", "subsections"] else pc.answer
        for pc in project.project_criteria
    } if project else {}

    with open('static/data/criteria_descriptions.json', 'r') as json_file:
        criteria_descriptions = json.load(json_file)

    return render_template(
        "questions.html",
        project=project,
        criteria=criteria,
        reporting_areas=reporting_areas,
        project_criteria_answers=project_criteria_answers,
        criteria_descriptions=criteria_descriptions
    )


@app.route("/longlist/<int:project_id>", methods=["GET", "POST"])
@login_required
def longlist(project_id):
    project = Project.query.get_or_404(project_id)

    # Load the reporting area methods from the JSON file
    with open("static/data/reporting_area.json", "r") as json_file:
        reporting_areas = json.load(json_file)["reporting_areas"]

    # Load the always applicable methods from the separate JSON file
    with open("static/data/methods.json", "r") as json_file:
        always_applicable_methods = json.load(json_file)["methods"]

    # Check for missing criteria
    if check_missing_criteria_answers(project):
        flash("Additional criteria have been added. Please answer the new questions before proceeding.", "warning")
        return redirect(url_for("questions", project_id=project.id))

    # Fetch project answers dynamically from ProjectCriteria
    project_answers = {
        pc.criteria.name: pc.answer.split(",") if pc.criteria.name in ["reporting_area", "subsections"] else pc.answer
        for pc in project.project_criteria
    }

    # Collect all methods from reporting areas
    reporting_area_methods = []
    for reporting_area in reporting_areas:
        for subsection in reporting_area.get("subsections", []):
            for method in subsection.get("methods", []):
                if "name" in method:
                    # Add reporting area and subsection information to the method
                    reporting_area_methods.append({
                        "reporting_area": reporting_area["name"],
                        "subsections": subsection["name"],
                        **method
                    })
                else:
                    app.logger.warning(
                        f"Method in subsection '{subsection['name']}' is missing a 'name' key and will be skipped."
                    )

    # Combine reporting area methods and always applicable methods
    all_methods = reporting_area_methods + always_applicable_methods

    # Define a function to determine if a method fits the project's answers
    def method_fits(method, project_answers):
        for criterion, answer in project_answers.items():
            field = method.get(criterion)
            # Handle reporting_area and subsections
            if criterion in ["reporting_area", "subsections"]:
                if field and field not in answer:
                    return False
            elif field and "levels" in field:
                # Check other criteria (budget, skills, etc.)
                if answer not in field["levels"]:
                    return False
        return True

    # Define a function to check if a method is "beyond capacity"
    def method_beyond_capacity(method, project_answers):
        # Priority mapping for levels
        LEVEL_PRIORITY = {"Low": 1, "Medium": 2, "High": 3}

        for criterion, answer in project_answers.items():
            # Skip phase_of_project as it does not have hierarchical levels
            if criterion == "phase_of_project":
                continue

            field = method.get(criterion)
            if field and "levels" in field:
                levels = field["levels"]

                # Filter levels to those present in LEVEL_PRIORITY
                valid_levels = [LEVEL_PRIORITY[level] for level in levels if level in LEVEL_PRIORITY]

                # Handle empty or invalid levels gracefully
                if not valid_levels:
                    app.logger.warning(
                        f"Levels for method '{method['name']}' in criterion '{criterion}' are invalid or empty.")
                    continue

                # Get the maximum priority of the method's levels
                max_method_priority = max(valid_levels)

                # Get the user's selected priority
                user_priority = LEVEL_PRIORITY.get(answer, 0)

                # If the user's priority exceeds the method's max, it is beyond capacity
                if user_priority > max_method_priority:
                    return True
        return False

    # Pre-index methods by name for faster lookups
    methods_by_name = {method["name"]: method for method in all_methods}

    # Categorize methods
    fitting_methods = [method for method in all_methods if method_fits(method, project_answers)]
    beyond_capacity_methods = [
        method for method in all_methods
        if method not in fitting_methods and method_beyond_capacity(method, project_answers)
    ]
    selected_methods = [t.technique_name for t in project.techniques]
    non_fitting_selected_methods = [
        method for method in all_methods
        if method["name"] in selected_methods and not method_fits(method, project_answers)
    ]

    if request.method == "POST":
        newly_selected_methods = request.form.getlist("technique")

        # Check if any non-fitting techniques are still selected
        non_fitting_selected_in_post = [
            method for method in non_fitting_selected_methods
            if method["name"] in newly_selected_methods
        ]

        if non_fitting_selected_in_post:
            flash("Warning: Some selected techniques do not fit the current criteria. Please review your selection.", "warning")
            return render_template(
                "longlist.html",
                fitting_methods=fitting_methods,
                beyond_capacity_methods=beyond_capacity_methods,
                non_fitting_selected_methods=non_fitting_selected_methods,
                selected_methods=newly_selected_methods,
                project_id=project.id,
                project=project,
            )

        # Add new selections
        for method_name in newly_selected_methods:
            if not SelectedTechnique.query.filter_by(project_id=project.id, technique_name=method_name).first():
                selected_method = methods_by_name.get(method_name)
                if selected_method:
                    new_selection = SelectedTechnique(
                        technique_name=selected_method["name"],
                        description=selected_method["description"],
                        image_filename=selected_method.get("photo"),
                        project_id=project.id,
                    )
                    db.session.add(new_selection)

        # Remove deselected methods
        for technique in project.techniques:
            if technique.technique_name not in newly_selected_methods:
                db.session.delete(technique)

        db.session.commit()
        return redirect(url_for("project", project_id=project.id))

    # Prepare reasons for non-fitting methods
    reasons = {}
    for method in non_fitting_selected_methods:
        reason = []
        for criterion, answer in project_answers.items():
            field = method.get(criterion)
            if field and "levels" in field and answer not in field["levels"]:
                reason.append(
                    f"Your selected {criterion.replace('_', ' ')} is '{answer}', "
                    f"but this method is suitable for {', '.join(field['levels'])}."
                )
        reasons[method["name"]] = " ".join(reason)

    return render_template(
        "longlist.html",
        fitting_methods=fitting_methods,
        beyond_capacity_methods=beyond_capacity_methods,
        non_fitting_selected_methods=non_fitting_selected_methods,
        reasons=reasons,
        selected_methods=selected_methods,
        project_id=project.id,
        project=project,
    )




@app.route("/project/<int:project_id>", methods=['GET'])
@login_required
def project(project_id):
    project = Project.query.get_or_404(project_id)

    # Check for missing criteria answers
    if check_missing_criteria_answers(project):
        flash("Additional criteria have been added. Please answer the new questions before proceeding.", "warning")
        return redirect(url_for('questions', project_id=project.id))

    # Fetch project criteria answers
    criteria_answers = {pc.criteria.name: pc.answer for pc in project.project_criteria}

    # Retrieve selected techniques for the project
    techniques = SelectedTechnique.query.filter_by(project_id=project.id).all()

    if not techniques:
        app.logger.warning(f"No techniques found for project ID {project_id}.")

    return render_template(
        'project.html',
        project=project,
        techniques=techniques,
        criteria_answers=criteria_answers
    )




@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('landing'))


@app.route("/delete_project/<int:project_id>", methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.owner != current_user:
        abort(403)
    db.session.delete(project)
    db.session.commit()
    flash('Your project has been deleted!', 'success')
    return redirect(url_for('account'))


@app.route("/project/<int:project_id>/technique/<string:technique_name>")
@login_required
def intervention(project_id, technique_name):
    project = Project.query.get_or_404(project_id)


    with open('static/data/reporting_area.json', 'r') as json_file:
        reporting_areas = json.load(json_file)
    # Assuming that techniques are directly related to the project
    technique = next((tech for tech in project.techniques if tech.technique_name == technique_name), None)
    if technique is None:
        abort(404)  # Technique not found in the project
    # Pass both `project` and `technique` to the template
    return render_template("intervention.html", project=project, technique=technique,
                           reporting_areas=reporting_areas)

@app.route("/project/<int:project_id>/technique/<string:technique_name>/remove", methods=['POST'])
@login_required
def remove_technique(project_id, technique_name):
    project = Project.query.get_or_404(project_id)
    technique = next((tech for tech in project.techniques if tech.technique_name == technique_name), None)

    if technique:
        db.session.delete(technique)
        db.session.commit()
        flash(f"Technique '{technique_name}' has been removed from the project.", "warning")
    else:
        flash(f"Technique '{technique_name}' not found in the project.", "danger")

    return redirect(url_for('project', project_id=project.id))

if __name__ == '__main__':
    app.run(debug=True)
