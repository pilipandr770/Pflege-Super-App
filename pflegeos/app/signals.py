"""
Database event signals for automated workflows
"""
from sqlalchemy import event
from app.extensions import db
from datetime import datetime, date


def init_signals(app):
    """Initialize all database event handlers"""

    # NOTE: Document generation is now handled in the route handler
    # (see app/routes/medications.py - new_plan route calls _create_medication_document)
    # This avoids SQLAlchemy transaction state issues with signals
    pass


def _generate_medication_document_content(medication_plan):
    """
    Generate the HTML content for a medication document
    """
    from app.models import Medication
    
    medications = Medication.query.filter_by(
        medication_plan_id=medication_plan.id,
        is_active=True
    ).all()
    
    # Генерируем HTML документ с информацией о медикаментах
    rows = []
    for med in medications:
        btm_badge = '<span class="badge bg-danger">BtM</span>' if med.is_btm else ''
        dosing = f"{med.morgens or '0'}–{med.mittags or '0'}–{med.abends or '0'}–{med.nachts or '0'}"
        
        rows.append(f"""
        <tr>
            <td><strong>{med.handelsname}</strong><br><small class="text-muted">{med.wirkstoff or ''}</small></td>
            <td>{med.staerke or '—'}</td>
            <td>{med.darreichungsform or '—'}</td>
            <td><code>{dosing}</code></td>
            <td>{med.einnahmehinweis or '—'}</td>
            <td>{btm_badge}</td>
        </tr>
        """)
    
    meds_table = ''.join(rows) if rows else '<tr><td colspan="6" class="text-muted">Keine Medikamente</td></tr>'
    
    html_content = f"""
    <div class="medication-document">
        <h5>Medikationsplan</h5>
        <div class="medication-info mb-3">
            <p><strong>Gültig ab:</strong> {medication_plan.valid_from.strftime('%d.%m.%Y')}</p>
            <p><strong>Verordnender Arzt:</strong> {medication_plan.prescribed_by or '—'}</p>
            <p><strong>Erstellt von:</strong> {medication_plan.creator.full_name if medication_plan.creator else '—'}</p>
        </div>
        
        <table class="table table-sm">
            <thead>
                <tr>
                    <th>Medikament</th>
                    <th>Stärke</th>
                    <th>Form</th>
                    <th>Dosierung (M–Mi–A–N)</th>
                    <th>Hinweis</th>
                    <th>BtM</th>
                </tr>
            </thead>
            <tbody>
                {meds_table}
            </tbody>
        </table>
        
        <div class="document-meta text-muted small">
            <p>Automatisch erstellt am {datetime.utcnow().strftime('%d.%m.%Y %H:%M')} Uhr</p>
        </div>
    </div>
    """
    
    return html_content
