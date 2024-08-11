from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import tensorflow as tf
from werkzeug.utils import secure_filename
import json
from datetime import datetime
# from flask_migrate import Migrate

#region Initialisations : 
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configuring SQLite Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# migrate = Migrate(app, db)
# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'h5'}
#endregion

#? ******************************************
#? |                Models                  |
#? ******************************************

#region : Models 
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    models = db.relationship('Model', backref='owner', lazy=True)

class Model(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(1000),nullable=True)
    model_file = db.Column(db.String(150), nullable=False)  # Path to the saved model file
    fields = db.Column(db.Text, nullable=False)  # JSON-encoded string with form fields configuration
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

#endregion Models

#? ******************************************
#? |            Authentification            |
#? ******************************************
#region : 

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('catalog'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

#endregion

#? ******************************************
#? |              Main app routes           |
#? ******************************************

@app.route('/')
@login_required
def index():
    return render_template('index.html', name=current_user.username)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_model():
    print("[REQUEST] :",request.form)
    # fields_data=""
    if request.method == 'POST':
    #     try:
    #         fields = request.form.get('input_fields')  # Use get to avoid KeyError
    #         if fields:
    #             fields_data = json.loads(fields)  # Assuming fields is a JSON string
    #             # Process the fields data
    #         else:
    #             return "No fields data provided", 400
    #     except json.JSONDecodeError:
    #         return "Invalid JSON format", 400
        
        model_name = request.form['model_name']
        model_description = request.form['description']
        
        fields = request.form.get("input_fields")
        
        # input_fields = request.form.get("input_fields")
        # fields = json.loads(input_fields)  # Assuming this is JSON-encoded string
        
        model_file = request.files['model_file']

        if model_file and model_name:
            # Save the model file to the server
            model_filename = secure_filename(model_file.filename).split(".")[0] +"_"+str(datetime.now()).replace(" ",'_').replace(":","-")[:16]+".h5"
            model_path = os.path.join('uploads/models', model_filename)
            model_file.save(model_path)
            
            # Create a new Model instance and save it to the database
            new_model = Model(
                model_name=model_name,
                model_file=model_path,
                description = model_description,
                fields=fields,
                owner=current_user
            )
            db.session.add(new_model)
            db.session.commit()

            flash('Model uploaded successfully!')
            return redirect(url_for('catalog'))

    return render_template('upload.html')

@app.route('/catalog')
@login_required
def catalog():
    user_models = Model.query.filter_by(user_id=current_user.id).all()
    return render_template('catalog.html', models=user_models)

@app.route('/model/<int:model_id>',methods=['GET', 'POST'])
@login_required
def model_details(model_id):
    model = Model.query.get(model_id)
    if not model:
        return "Model not found", 404

    # Deserialize fields from JSON string
    input_fields = json.loads(model.fields)
    if request.method == 'POST':
        try :
            model = tf.keras.models.load_model(model.model_file)
            input_data = request.form.to_dict()
            input_data = [float(input_data[field['name']]) if field['type'] == 'number' 
                        else input_data[field['name']] for field in input_fields]
            input_data = [input_data]  # Model expects a batch dimension
            prediction = model.predict(input_data)
            predicted_label = prediction.argmax(axis=-1)[0]
            return json.dumps({"prediction": str(predicted_label)})
        except Exception as e:
            return str(e)

    return render_template('model_details.html', model=model, input_fields=input_fields)

# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()  # Ensure all tables are created
#         print(db.inspect(db.engine).get_table_names())

#     app.run()
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure all tables are created
        print(db.inspect(db.engine).get_table_names())

    app.run(port = 8000,debug=True)