"""
Public pages — accessible without login.
Routes: /impressum, /agb, /datenschutz, /offline, /static/icons/*
The landing page (/) is handled in dashboard.index with an auth check.
"""
from flask import Blueprint, render_template, send_from_directory, current_app
import os

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


@public_bp.route('/offline')
def offline():
    return render_template('pwa/offline.html')


@public_bp.route('/sw.js')
def service_worker():
    """Service Worker muss vom Root ausgeliefert werden (Scope!)."""
    static_folder = os.path.join(current_app.root_path, 'static')
    return send_from_directory(static_folder, 'sw.js',
                               mimetype='application/javascript')
