# Login/logout is handled by hanson/routes/auth.py via vas3k.club OIDC.
# This module is kept as an empty Blueprint placeholder.
from flask import Blueprint

app = Blueprint(name="session", import_name=__name__)
