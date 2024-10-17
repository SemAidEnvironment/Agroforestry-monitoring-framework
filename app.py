from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pandas as pd


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
    project = Project.query.get(project_id) if project_id else None
    criteria = Criteria.query.all()  # Fetch all available criteria

    # If the request is POST, either create a new project or update existing criteria
    if request.method == "POST":
        if not project:
            # If no project exists, create a new project with a name
            project_name = request.form.get("project_name")
            project = Project(name=project_name, owner=current_user)
            db.session.add(project)
            db.session.commit()  # Save to generate the project ID

        # Save or update criteria answers
        for criterion in criteria:
            answer = request.form.get(f"criteria_{criterion.id}")
            if answer:
                project_criteria = ProjectCriteria.query.filter_by(
                    project_id=project.id, criteria_id=criterion.id
                ).first()

                if project_criteria:
                    project_criteria.answer = answer
                else:
                    new_project_criteria = ProjectCriteria(
                        project_id=project.id, criteria_id=criterion.id, answer=answer
                    )
                    db.session.add(new_project_criteria)

        db.session.commit()
        return redirect(url_for("longlist", project_id=project.id))

    # Fetch existing answers for the project
    project_criteria_answers = {pc.criteria_id: pc.answer for pc in project.project_criteria} if project else {}

    return render_template("questions.html", project=project, criteria=criteria,
                           project_criteria_answers=project_criteria_answers)


@app.route("/longlist/<int:project_id>", methods=['GET', 'POST'])
@login_required
def longlist(project_id):
    project = Project.query.get(project_id) if project_id else None
    # Check if there are any missing criteria answers
    if check_missing_criteria_answers(project):
        flash("Additional criteria have been added. Please answer the new questions before proceeding.", "warning")
        return redirect(url_for('questions', project_id=project.id))
    project = Project.query.get_or_404(project_id)
    techniques_df = pd.read_excel('data/techniques.xlsx')

    # Fetch the project answers dynamically from ProjectCriteria
    project_answers = {
        pc.criteria.name: pc.answer for pc in project.project_criteria
    }

    selected_techniques = [t.technique_name for t in project.techniques]

    # Define a function to determine if a technique fits the project's answers dynamically
    def technique_fits(technique, project_answers):
        for criterion, answer in project_answers.items():
            if pd.notna(technique.get(criterion)) and answer not in str(technique.get(criterion)).split(','):
                return False
        return True

    # Filter techniques that fit the criteria
    fitting_techniques = techniques_df[techniques_df.apply(lambda x: technique_fits(x, project_answers), axis=1)]

    # Find techniques that were selected but no longer fit
    non_fitting_selected_techniques = techniques_df[
        ~techniques_df.apply(lambda x: technique_fits(x, project_answers), axis=1) &
        techniques_df['technique_name'].isin(selected_techniques)
        ]

    if request.method == 'POST':
        newly_selected_techniques = request.form.getlist('technique')

        # Add new selections
        for technique_name in newly_selected_techniques:
            if technique_name not in selected_techniques:
                description = techniques_df[techniques_df['technique_name'] == technique_name]['description'].values[0]
                image_filename = \
                techniques_df[techniques_df['technique_name'] == technique_name]['image_filename'].values[0]
                selected = SelectedTechnique(
                    technique_name=technique_name,
                    description=description,
                    image_filename=image_filename,
                    project_id=project.id
                )
                db.session.add(selected)

        # Remove deselected techniques
        for technique in project.techniques:
            if technique.technique_name not in newly_selected_techniques:
                db.session.delete(technique)

        db.session.commit()
        return redirect(url_for('project', project_id=project.id, project =project))

    # Prepare reasons for non-fitting techniques
    reasons = {}
    for index, technique in non_fitting_selected_techniques.iterrows():
        reason = []
        for criterion, answer in project_answers.items():
            if pd.notna(technique.get(criterion)) and answer not in str(technique.get(criterion)).split(','):
                reason.append(
                    f"Your selected {criterion.replace('_', ' ')} is '{answer}'. However, this technique is suitable for '{technique.get(criterion)}'."
                )
        reasons[technique['technique_name']] = ' '.join(reason)

    return render_template('longlist.html',
                           fitting_techniques=fitting_techniques.to_dict('records'),
                           non_fitting_selected_techniques=non_fitting_selected_techniques.to_dict('records'),
                           reasons=reasons,
                           selected_techniques=selected_techniques,
                           project_id=project.id,
                           project=project)

@app.route("/project/<int:project_id>")
@login_required
def project(project_id):
    project = Project.query.get(project_id) if project_id else None
    # Check if there are any missing criteria answers
    if check_missing_criteria_answers(project):
        flash("Additional criteria have been added. Please answer the new questions before proceeding.", "warning")
        return redirect(url_for('questions', project_id=project.id))
    project = Project.query.get_or_404(project_id)
    criteria_answers = {pc.criteria.name: pc.answer for pc in project.project_criteria}
    techniques = SelectedTechnique.query.filter_by(project_id=project.id).all()
    return render_template('project.html', project=project, techniques=techniques, criteria_answers=criteria_answers)


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
    # Assuming that techniques are directly related to the project
    technique = next((tech for tech in project.techniques if tech.technique_name == technique_name), None)
    if technique is None:
        abort(404)  # Technique not found in the project
    # Pass both `project` and `technique` to the template
    return render_template("intervention.html", project=project, technique=technique)

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
