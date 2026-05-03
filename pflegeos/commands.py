"""
Flask CLI команды.
Использование:
  flask seed          — заполняет Leistungskatalog для всех компаний
  flask create-admin  — создаёт первого admin вручную (если забыли пароль)
"""
import click
from flask import current_app
from app import create_app
from app.extensions import db

app = create_app()


@app.cli.command("seed")
def seed_command():
    """Füllt Standard-Leistungskatalog für alle Einrichtungen."""
    from seed import seed_all
    seed_all()
    click.echo("✓ Leistungskatalog-Seeding abgeschlossen.")


@app.cli.command("create-admin")
@click.argument("company_email")
@click.argument("admin_email")
@click.argument("password")
def create_admin(company_email, admin_email, password):
    """Erstellt oder setzt Admin-Passwort zurück."""
    from app.models import Company, Employee
    company = Company.query.filter_by(email=company_email).first()
    if not company:
        click.echo(f"Einrichtung nicht gefunden: {company_email}")
        return
    emp = Employee.query.filter_by(email=admin_email, company_id=company.id).first()
    if emp:
        emp.set_password(password)
        emp.role = 'ADMIN'
        emp.is_active = True
        db.session.commit()
        click.echo(f"✓ Passwort zurückgesetzt: {admin_email}")
    else:
        click.echo(f"Mitarbeiter nicht gefunden: {admin_email}")
