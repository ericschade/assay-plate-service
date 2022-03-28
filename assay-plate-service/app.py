from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow

# Init App
app = Flask(__name__)
# Database config
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///assay-plate-service.db"

# Init db
db = SQLAlchemy(app)
# Init Marshmallow
ma = Marshmallow(app)

from routes import *


# Run Server
if __name__ == '__main__':
    app.run(debug=True)