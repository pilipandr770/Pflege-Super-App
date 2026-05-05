"""
Angehörigen-Portal — öffentlicher Magic-Link-Zugang für Familienangehörige.
Keine Authentifizierung erforderlich, nur ein eindeutiger portal_token.
Zeigt eine gefilterte Besuchsübersicht ohne medizinische / Abrechnungsdaten.
"""

from flask import Blueprint, render_template, abort
from app.models import Patient, Leistungsnachweis, VisitReport, PatientPhoto
from app.extensions import db
from datetime import date, timedelta
import json

family_bp = Blueprint('family', __name__, url_prefix='/familie')


@family_bp.route('/<token>')
def portal(token):
    """Angehörigen-Portal: öffentliche Besuchsübersicht."""
    patient = Patient.query.filter_by(
        portal_token=token,
        portal_enabled=True,
        deleted_at=None
    ).first()

    if not patient:
        abort(404)

    # Letzte 60 Tage
    since = date.today() - timedelta(days=60)

    # ── VisitReports (aus Schedule-Flow) ──
    visit_reports = VisitReport.query.filter(
        VisitReport.patient_id == patient.id,
        VisitReport.is_active == True,
        VisitReport.status.in_(['SUBMITTED', 'VERIFIED']),
        VisitReport.visit_date >= since
    ).order_by(VisitReport.visit_date.desc()).all()

    # Fotos nur wenn Einwilligung erteilt
    visit_photo_map = {}
    if patient.einwilligung_foto:
        for vr in visit_reports:
            try:
                ids = json.loads(vr.photo_ids or '[]')
                if ids:
                    photos = PatientPhoto.query.filter(
                        PatientPhoto.id.in_(ids),
                        PatientPhoto.is_active == True,
                        PatientPhoto.photo_type.notin_(['WOUND', 'PRESSURE_ULCER'])
                    ).all()
                    if photos:
                        visit_photo_map[vr.id] = photos
            except Exception:
                pass

    # ── Leistungsnachweise (manuelle Einträge) ──
    leistungen = Leistungsnachweis.query.filter(
        Leistungsnachweis.patient_id == patient.id,
        Leistungsnachweis.durchgefuehrt_am >= since
    ).order_by(Leistungsnachweis.durchgefuehrt_am.desc()).all()

    # Letzter Besuch
    last_visit_date = None
    if visit_reports:
        last_visit_date = visit_reports[0].visit_date
    elif leistungen:
        last_visit_date = leistungen[0].durchgefuehrt_am

    return render_template('family/portal.html',
                           patient=patient,
                           visit_reports=visit_reports,
                           leistungen=leistungen,
                           visit_photo_map=visit_photo_map,
                           last_visit_date=last_visit_date,
                           today=date.today())
