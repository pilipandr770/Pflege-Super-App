"""
Hausarzt-Portal — Magic-Link für externe Ärzte.
Kein Login erforderlich. Arzt kann den Medikamentenplan seines Patienten
einsehen und aktualisieren (hinzufügen / absetzen / Hinweise hinterlassen).
BtM-Medikamente: nur Lesezugriff.
"""

from flask import Blueprint, render_template, request, redirect, url_for, abort, flash
from app.models import Patient, MedicationPlan, Medication
from app.extensions import db
from app.utils.auth import log_action
from datetime import datetime, date

doctor_bp = Blueprint('doctor', __name__, url_prefix='/arzt')


def _get_patient_by_token(token):
    """Gibt Patienten zurück, wenn Token gültig und Portal aktiv."""
    p = Patient.query.filter_by(
        arzt_token=token,
        arzt_portal_enabled=True,
        deleted_at=None
    ).first()
    if not p:
        abort(404)
    return p


def _current_plan(patient):
    """Gibt den aktuellen Medikamentenplan zurück (oder erstellt einen neuen)."""
    plan = MedicationPlan.query.filter_by(
        patient_id=patient.id,
        is_current=True
    ).first()
    return plan


# ── Hauptseite ──────────────────────────────────────────────────────────────

@doctor_bp.route('/<token>')
def portal(token):
    patient = _get_patient_by_token(token)
    plan    = _current_plan(patient)
    meds    = plan.medications.filter_by(is_active=True).all() if plan else []
    stopped = plan.medications.filter_by(is_active=False).all() if plan else []

    return render_template('doctor/portal.html',
                           patient=patient,
                           plan=plan,
                           meds=meds,
                           stopped=stopped,
                           token=token,
                           today=date.today())


# ── Medikament hinzufügen ───────────────────────────────────────────────────

@doctor_bp.route('/<token>/add', methods=['POST'])
def add_medication(token):
    patient = _get_patient_by_token(token)
    plan    = _current_plan(patient)

    # Falls kein Plan existiert: neuen erstellen
    if not plan:
        plan = MedicationPlan(
            company_id=patient.company_id,
            patient_id=patient.id,
            created_by=None,          # externer Arzt — kein Employee-FK
            prescribed_by=patient.hausarzt_name or 'Hausarzt (extern)',
            valid_from=date.today(),
            is_current=True,
        )
        db.session.add(plan)
        db.session.flush()

    f = request.form
    handelsname = f.get('handelsname', '').strip()
    if not handelsname:
        flash('Handelsname ist Pflichtfeld.', 'danger')
        return redirect(url_for('doctor.portal', token=token))

    med = Medication(
        medication_plan_id=plan.id,
        handelsname=handelsname,
        wirkstoff=f.get('wirkstoff', '').strip(),
        staerke=f.get('staerke', '').strip(),
        darreichungsform=f.get('darreichungsform', '').strip(),
        pzn=f.get('pzn', '').strip(),
        morgens=f.get('morgens', '').strip(),
        mittags=f.get('mittags', '').strip(),
        abends=f.get('abends', '').strip(),
        nachts=f.get('nachts', '').strip(),
        bei_bedarf='bei_bedarf' in f,
        bei_bedarf_max=f.get('bei_bedarf_max', '').strip(),
        einnahmehinweis=f.get('einnahmehinweis', '').strip(),
        is_btm=False,
        is_active=True,
    )
    db.session.add(med)

    # Arzt-Aktivität auf Patient markieren
    patient.arzt_last_update = datetime.utcnow()
    # Plan: prescribed_by aktualisieren
    plan.prescribed_by = patient.hausarzt_name or 'Hausarzt (extern)'
    plan.updated_at = datetime.utcnow()

    db.session.commit()

    # Audit (ohne Employee-ID — externer Arzt)
    try:
        from app.utils.auth import log_action
        log_action('ARZT_MED_ADDED', 'Medication', med.id, new_values={
            'patient': patient.full_name,
            'medikament': handelsname,
            'arzt': patient.hausarzt_name or 'extern',
        })
    except Exception:
        pass

    flash(f'✓ {handelsname} wurde dem Medikamentenplan hinzugefügt.', 'success')
    return redirect(url_for('doctor.portal', token=token))


# ── Medikament absetzen ─────────────────────────────────────────────────────

@doctor_bp.route('/<token>/stop/<med_id>', methods=['POST'])
def stop_medication(token, med_id):
    patient = _get_patient_by_token(token)
    plan    = _current_plan(patient)
    if not plan:
        abort(404)

    med = Medication.query.filter_by(
        id=med_id,
        medication_plan_id=plan.id,
        is_btm=False   # BtM darf nur intern abgesetzt werden
    ).first_or_404()

    reason = request.form.get('reason', '').strip()
    med.is_active = False
    med.einnahmehinweis = (med.einnahmehinweis or '') + \
        f'\n[Abgesetzt {date.today().strftime("%d.%m.%Y")} durch Hausarzt' + \
        (f': {reason}' if reason else '') + ']'

    patient.arzt_last_update = datetime.utcnow()
    db.session.commit()

    try:
        log_action('ARZT_MED_STOPPED', 'Medication', med_id, new_values={
            'patient': patient.full_name,
            'medikament': med.handelsname,
            'reason': reason,
        })
    except Exception:
        pass

    flash(f'✓ {med.handelsname} wurde abgesetzt.', 'success')
    return redirect(url_for('doctor.portal', token=token))


# ── Allgemeine Hinweise speichern ───────────────────────────────────────────

@doctor_bp.route('/<token>/note', methods=['POST'])
def save_note(token):
    patient = _get_patient_by_token(token)
    plan    = _current_plan(patient)
    if not plan:
        flash('Kein aktiver Medikamentenplan gefunden.', 'warning')
        return redirect(url_for('doctor.portal', token=token))

    note = request.form.get('arzt_hinweis', '').strip()
    if note:
        # Note wird in prescribed_by + neuem Feld gespeichert
        # (wir nutzen plan.prescribed_by als Freitext — bestehende Struktur)
        plan.prescribed_by = (patient.hausarzt_name or 'Hausarzt') + \
            f' — Hinweis {date.today().strftime("%d.%m.%Y")}: {note}'
        patient.arzt_last_update = datetime.utcnow()
        db.session.commit()
        flash('✓ Hinweis gespeichert und für Pflegepersonal sichtbar.', 'success')

    return redirect(url_for('doctor.portal', token=token))
