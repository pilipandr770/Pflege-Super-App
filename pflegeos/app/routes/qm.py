"""
Qualitätsmanagement — MDK-Prüfungen und interne QM-Checklisten.
Nur für ADMIN.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import QmPruefung, QmPruefungItem
from app.utils.auth import admin_required, log_action
from datetime import date, datetime

qm_bp = Blueprint('qm', __name__, url_prefix='/qm')

# ── MDK-Standardkatalog (SGB XI §114) ────────────────────────────────────────

MDK_KATALOG = [
    # Kategorie, Kriterium
    ('Pflege',          'Individuelle Pflegeplanung vorhanden und aktuell'),
    ('Pflege',          'Pflegeziele werden regelmäßig evaluiert'),
    ('Pflege',          'Maßnahmen zur Dekubitusprophylaxe durchgeführt'),
    ('Pflege',          'Sturzprophylaxe dokumentiert und umgesetzt'),
    ('Pflege',          'Schmerzmanagement dokumentiert'),
    ('Pflege',          'Ernährung und Flüssigkeitszufuhr protokolliert'),
    ('Pflege',          'Mundpflege regelmäßig durchgeführt'),
    ('Dokumentation',   'Pflegebericht aktuell und vollständig'),
    ('Dokumentation',   'Leistungsnachweise vollständig vorhanden'),
    ('Dokumentation',   'SIS (Strukturierte Informationssammlung) aktuell'),
    ('Dokumentation',   'Medikationsplan aktuell und ärztlich angeordnet'),
    ('Dokumentation',   'Einwilligungen (Foto, Datenschutz) vorhanden'),
    ('Hygiene',         'Handhygiene-Standards eingehalten'),
    ('Hygiene',         'Schutzausrüstung korrekt verwendet'),
    ('Hygiene',         'Wundversorgung aseptisch durchgeführt'),
    ('Hygiene',         'Medikamentenlagerung korrekt'),
    ('Kommunikation',   'Angehörige regelmäßig informiert'),
    ('Kommunikation',   'Hausarzt bei Veränderungen informiert'),
    ('Kommunikation',   'Übergabegespräche dokumentiert'),
    ('Personal',        'Qualifikationsnachweise vorhanden'),
    ('Personal',        'Fortbildungen aktuell (≤ 2 Jahre)'),
    ('Personal',        'Dienstplan eingehalten'),
]


# ── Liste ─────────────────────────────────────────────────────────────────────

@qm_bp.route('/')
@login_required
@admin_required
def index():
    pruefungen = QmPruefung.query.filter_by(
        company_id=current_user.company_id
    ).order_by(QmPruefung.datum.desc()).all()
    return render_template('qm/index.html', pruefungen=pruefungen)


# ── Neue Prüfung ──────────────────────────────────────────────────────────────

@qm_bp.route('/neu', methods=['GET', 'POST'])
@login_required
@admin_required
def neu():
    if request.method == 'POST':
        fd = request.form
        typ   = fd.get('typ', 'INTERN')
        titel = fd.get('titel', '').strip()
        if not titel:
            flash('Titel ist ein Pflichtfeld.', 'danger')
            return render_template('qm/form.html', today=date.today())

        pruefung = QmPruefung(
            company_id=current_user.company_id,
            created_by=current_user.id,
            typ=typ,
            titel=titel,
            datum=_parse_date(fd.get('datum')) or date.today(),
            pruefer=fd.get('pruefer', '').strip() or None,
            status='OFFEN',
        )
        db.session.add(pruefung)
        db.session.flush()

        # MDK-Katalog vorladen wenn gewünscht
        if fd.get('mdk_vorladen') == '1':
            for i, (kat, krit) in enumerate(MDK_KATALOG):
                item = QmPruefungItem(
                    pruefung_id=pruefung.id,
                    kategorie=kat,
                    kriterium=krit,
                    ergebnis='OK',
                    sort_order=i,
                )
                db.session.add(item)

        db.session.commit()
        log_action('CREATE', 'qm_pruefungen', entity_id=pruefung.id)
        flash('Prüfung angelegt.', 'success')
        return redirect(url_for('qm.show', pruefung_id=pruefung.id))

    return render_template('qm/form.html', today=date.today())


# ── Prüfung anzeigen / bearbeiten ────────────────────────────────────────────

@qm_bp.route('/<pruefung_id>')
@login_required
@admin_required
def show(pruefung_id):
    pruefung = _get_pruefung(pruefung_id)
    items = pruefung.items.order_by(
        QmPruefungItem.kategorie, QmPruefungItem.sort_order
    ).all()

    # Gruppieren nach Kategorie
    kategorien: dict = {}
    for item in items:
        kategorien.setdefault(item.kategorie, []).append(item)

    return render_template('qm/show.html',
                           pruefung=pruefung,
                           kategorien=kategorien)


# ── Prüfpunkt speichern (AJAX) ───────────────────────────────────────────────

@qm_bp.route('/item/<item_id>/update', methods=['POST'])
@login_required
@admin_required
def update_item(item_id):
    item = QmPruefungItem.query.join(QmPruefung).filter(
        QmPruefungItem.id == item_id,
        QmPruefung.company_id == current_user.company_id,
    ).first_or_404()

    item.ergebnis  = request.form.get('ergebnis', item.ergebnis)
    item.bemerkung = request.form.get('bemerkung', '').strip() or None
    item.massnahme = request.form.get('massnahme', '').strip() or None
    db.session.commit()

    return jsonify({
        'ok': True,
        'ergebnis': item.ergebnis,
        'pruefung_id': item.pruefung_id,
    })


# ── Prüfpunkt hinzufügen ──────────────────────────────────────────────────────

@qm_bp.route('/<pruefung_id>/item/neu', methods=['POST'])
@login_required
@admin_required
def add_item(pruefung_id):
    pruefung = _get_pruefung(pruefung_id)
    fd = request.form
    kriterium = fd.get('kriterium', '').strip()
    if not kriterium:
        flash('Kriterium darf nicht leer sein.', 'danger')
        return redirect(url_for('qm.show', pruefung_id=pruefung_id))

    item = QmPruefungItem(
        pruefung_id=pruefung.id,
        kategorie=fd.get('kategorie', 'Sonstiges').strip(),
        kriterium=kriterium,
        ergebnis='OK',
        sort_order=pruefung.items.count(),
    )
    db.session.add(item)
    db.session.commit()
    flash('Prüfpunkt hinzugefügt.', 'success')
    return redirect(url_for('qm.show', pruefung_id=pruefung_id))


# ── Prüfung abschließen ───────────────────────────────────────────────────────

@qm_bp.route('/<pruefung_id>/abschliessen', methods=['POST'])
@login_required
@admin_required
def abschliessen(pruefung_id):
    pruefung = _get_pruefung(pruefung_id)
    fd = request.form
    pruefung.status          = 'ABGESCHLOSSEN'
    pruefung.gesamtergebnis  = fd.get('gesamtergebnis', '').strip() or None
    pruefung.massnahmen      = fd.get('massnahmen', '').strip() or None
    pruefung.updated_at      = datetime.utcnow()
    db.session.commit()
    log_action('QM_ABGESCHLOSSEN', 'qm_pruefungen', entity_id=pruefung_id)
    flash('Prüfung abgeschlossen.', 'success')
    return redirect(url_for('qm.show', pruefung_id=pruefung_id))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_pruefung(pruefung_id):
    return QmPruefung.query.filter_by(
        id=pruefung_id,
        company_id=current_user.company_id,
    ).first_or_404()


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except Exception:
        return None
