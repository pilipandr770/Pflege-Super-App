"""
Public pages — accessible without login.
Routes: /impressum, /agb, /datenschutz
The landing page (/) is handled in dashboard.index with an auth check.
"""
from flask import Blueprint, render_template

public_bp = Blueprint('public', __name__)


@public_bp.route('/impressum')
def impressum():
    return render_template('public/impressum.html')


@public_bp.route('/agb')
def agb():
    return render_template('public/agb.html')


@public_bp.route('/datenschutz')
def datenschutz():
    return render_template('public/datenschutz.html')
