"""
seed.py — Setzt Standard-Leistungskatalog für eine Einrichtung.
Aufruf: flask seed  oder  python seed.py <company_id>
"""
import sys
from app import create_app
from app.extensions import db
from app.models import Leistungskatalog, Company, Employee

STANDARD_LEISTUNGEN = [
    # Körperpflege
    ("LK01", "Vollbad / Dusche", "Körperpflege", "Vollständige Körperreinigung inkl. Haare", 30),
    ("LK02", "Teilwäsche / Waschen am Bett", "Körperpflege", "Teilkörperpflege oder Waschen im Bett", 20),
    ("LK03", "Mundpflege", "Körperpflege", "Zahn- und Mundpflege, Prothesenpflege", 10),
    ("LK04", "Haarpflege", "Körperpflege", "Haare waschen und kämmen", 15),
    ("LK05", "Intimpflege", "Körperpflege", "Intim- und Inkontinenzpflege", 10),
    ("LK06", "Rasieren", "Körperpflege", "Gesichtsrasur", 10),
    ("LK07", "Nagelpflege", "Körperpflege", "Fingernagel- und Fußnagelpflege", 15),
    # An-/Auskleiden
    ("LK10", "An- und Auskleiden", "Mobilisation", "Hilfe beim An- und Ausziehen", 15),
    # Mobilisation
    ("LK15", "Mobilisation / Transfer", "Mobilisation", "Aufstehen, Umsetzen, Gehen begleiten", 15),
    ("LK16", "Lagerung / Positionswechsel", "Mobilisation", "Druckentlastungslagerung, Positionierung", 10),
    ("LK17", "Kontrakturprophylaxe", "Mobilisation", "Passives und aktives Bewegungstraining", 20),
    # Ernährung
    ("LK20", "Essensvorbereitung / Anreichen", "Ernährung", "Essen vorbereiten und beim Essen helfen", 20),
    ("LK21", "Sondenkost verabreichen", "Ernährung", "Ernährung über Sonde (PEG/NGS)", 15),
    ("LK22", "Trinken reichen / Flüssigkeitsbilanz", "Ernährung", "Flüssigkeitszufuhr sicherstellen und bilanzieren", 10),
    # Ausscheidung
    ("LK25", "Toilettengang begleiten", "Ausscheidung", "Hilfe beim Toilettengang", 10),
    ("LK26", "Inkontinenzversorgung", "Ausscheidung", "Versorgung bei Harn- und Stuhlinkontinenz", 10),
    ("LK27", "Katheterversorgung", "Ausscheidung", "Pflege und Überwachung von Blasenkathetern", 15),
    # Medikamente
    ("LK30", "Medikamentengabe oral", "Medikamente", "Orale Medikamentengabe und Dokumentation", 10),
    ("LK31", "Medikamentengabe subkutan/intramuskulär", "Medikamente", "Injektion und Dokumentation (Behandlungspflege)", 10),
    ("LK32", "Insulingabe", "Medikamente", "Insulinverabreichung inkl. Blutzuckerkontrolle", 15),
    ("LK33", "Inhalationstherapie", "Medikamente", "Inhalation mit Vernebler oder Spray", 10),
    # Behandlungspflege
    ("LK40", "Verbandwechsel einfach", "Behandlungspflege", "Einfacher Verbandwechsel nach ärztlicher Anordnung", 15),
    ("LK41", "Verbandwechsel komplex / Wundversorgung", "Behandlungspflege", "Komplexe Wundversorgung nach Wundtherapieplan", 30),
    ("LK42", "Kompressionsversorgung", "Behandlungspflege", "An- und Ausziehen von Kompressionsstrümpfen", 15),
    ("LK43", "Blutzuckermessung", "Behandlungspflege", "Blutzuckerkontrolle und Dokumentation", 5),
    ("LK44", "Blutdruckmessung", "Behandlungspflege", "Blutdruck- und Pulsmessung", 5),
    ("LK45", "Gewichtskontrolle", "Behandlungspflege", "Wiegen und Dokumentation", 10),
    # Soziale Betreuung
    ("LK50", "Betreuungsgespräch", "Soziale Betreuung", "Gespräch, Zuwendung und soziale Betreuung", 20),
    ("LK51", "Aktivierung / Beschäftigung", "Soziale Betreuung", "Aktivierende Betreuung und Beschäftigungsangebote", 30),
    ("LK52", "Gedächtnisübungen / Kognitive Aktivierung", "Soziale Betreuung", "Kognitive Förderung (Demenzpflege)", 20),
    # Hauswirtschaft (ambulant)
    ("LK60", "Reinigung Wohnbereich", "Hauswirtschaft", "Wohnreinigung", 30),
    ("LK61", "Wäschepflege", "Hauswirtschaft", "Waschen, Trocknen, Zusammenlegen", 20),
    ("LK62", "Einkauf", "Hauswirtschaft", "Einkaufen nach Wunsch", 45),
    ("LK63", "Mahlzeiten zubereiten", "Hauswirtschaft", "Kochen und Mahlzeitenvorbereitung", 30),
]


def seed_leistungen(company_id):
    count = 0
    for nr, name, kat, beschr, dauer in STANDARD_LEISTUNGEN:
        exists = Leistungskatalog.query.filter_by(
            company_id=company_id, leistung_nr=nr).first()
        if not exists:
            item = Leistungskatalog(
                company_id=company_id,
                leistung_nr=nr,
                bezeichnung=name,
                kategorie=kat,
                beschreibung=beschr,
                dauer_minuten=dauer,
                is_active=True,
            )
            db.session.add(item)
            count += 1
    db.session.commit()
    print(f"  ✓ {count} Leistungen hinzugefügt für company_id={company_id}")


def seed_all():
    """Alle Einrichtungen ohne Leistungskatalog befüllen."""
    companies = Company.query.all()
    for c in companies:
        existing = Leistungskatalog.query.filter_by(company_id=c.id).count()
        if existing == 0:
            print(f"Seeding: {c.name}")
            seed_leistungen(c.id)
        else:
            print(f"Skip (schon {existing} Einträge): {c.name}")


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        if len(sys.argv) > 1:
            seed_leistungen(sys.argv[1])
        else:
            seed_all()
