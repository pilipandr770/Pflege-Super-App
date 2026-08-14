"""
Sturzprotokoll — Dokumentation von Sturzereignissen.
Gesetzlich vorgeschrieben nach SGB XI und Heim-/Qualitätsprüfungsrichtlinien.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Sturzprotokoll, Patient, Employee
from app.utils.auth import log_action
from datetime import date, datetime

sturzprotokoll_bp = Blueprint('sturzprotokoll', __name__, url_prefix='/sturzprotokoll')

SEVERITY_LABELS = {
    'LEICHT': ('Leicht', 'success'),
    'MITTEL': ('Mittel', 'warning'),
    'SCHWER': ('Schwer', 'danger'),
}


@sturzprotokoll_bp.route('/patient/<patient_id>')
@login_required
def list_view(patient_id):
    patient = Patient.query.filter_by(
        id=patient_id, company_id=current_user.company_id, deleted_at=None
    ).first_or_404()

    protokolle = Sturzprotokoll.query.filter_by(
        company_id=current_user.company_id,
        patient_id=patient_id,
    ).order_by(Sturzprotokoll.sturz_datum.desc()).all()

    return render_template('sturzprotokoll/list.html',
                           patient=patient,
                           protokolle=protokolle,
                           severity_labels=SEVERITY_LABELS)


@sturzprotokoll_bp.route('/patient/<patient_id>/neu', methods=['GET', 'POST'])
@login_required
def neu(patient_id):
    patient = Patient.query.filter_by(
        id=patient_id, company_id=current_user.company_id, deleted_at=None
    ).first_or_404()

    errors = {}

    if request.method == 'POST':
        fd = request.form

        datum_str = fd.get('sturz_datum', '').strip()
        uhrzeit_str = fd.get('sturz_uhrzeit', '').strip()
        severity = fd.get('severity', 'MITTEL').strip()

        if not datum_str:
            errors['sturz_datum'] = 'Datum ist Pflichtfeld.'
        if severity not in SEVERITY_LABELS:
            errors['severity'] = 'Ungültige Schwere.'

        if not errors:
            try:
                sturz_datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
            except ValueError:
                errors['sturz_datum'] = 'Ungültiges Datum.'

        if not errors:
            sturz_uhrzeit = None
            if uhrzeit_str:
                try:
                    sturz_uhrzeit = datetime.strptime(uhrzeit_str, '%H:%M').time()
                except ValueError:
                    pass

            arzt_informiert = 'arzt_informiert' in fd
            angehoerige_informiert = 'angehoerige_informiert' in fd

            arzt_informiert_um = None
            if arzt_informiert:
                arzt_um_str = fd.get('arzt_informiert_um', '').strip()
                if arzt_um_str:
                    try:
                        arzt_informiert_um = datetime.strptime(arzt_um_str, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        pass

            protokoll = Sturzprotokoll(
                company_id=current_user.company_id,
                patient_id=patient_id,
                reported_by=current_user.id,
                sturz_datum=sturz_datum,
                sturz_uhrzeit=sturz_uhrzeit,
                fundort=fd.get('fundort', '').strip() or None,
                sturzursache=fd.get('sturzursache', '').strip() or None,
                verletzungen=fd.get('verletzungen', '').strip() or None,
                massnahmen_sofort=fd.get('massnahmen_sofort', '').strip() or None,
                arzt_informiert=arzt_informiert,
                arzt_informiert_um=arzt_informiert_um,
                angehoerige_informiert=angehoerige_informiert,
                severity=severity,
            )
            db.session.add(protokoll)
            db.session.commit()

            log_action('STURZPROTOKOLL_ERSTELLT', 'Sturzprotokoll', protokoll.id,
                       new_values={
                           'patient': patient.full_name,
                           'datum': datum_str,
                           'severity': severity,
                       })

            flash('Sturzprotokoll erfolgreich gespeichert.', 'success')
            return redirect(url_for('sturzprotokoll.list_view', patient_id=patient_id))

    return render_template('sturzprotokoll/form.html',
                           patient=patient,
                           errors=errors,
                           today=date.today().isoformat(),
                           severity_labels=SEVERITY_LABELS)


@sturzprotokoll_bp.route('/<protokoll_id>')
@login_required
def show(protokoll_id):
    protokoll = Sturzprotokoll.query.filter_by(
        id=protokoll_id, company_id=current_user.company_id
    ).first_or_404()

    patient = Patient.query.get_or_404(protokoll.patient_id)
    reporter = Employee.query.get(protokoll.reported_by)

    return render_template('sturzprotokoll/show.html',
                           protokoll=protokoll,
                           patient=patient,
                           reporter=reporter,
                           severity_labels=SEVERITY_LABELS)
