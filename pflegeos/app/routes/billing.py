"""
Billing — Stripe-Integration für monatliche Abonnements.

Routen:
  GET  /billing/              — Billing-Übersicht für Company-Admin
  POST /billing/checkout      — Startet Stripe Checkout Session
  GET  /billing/success       — Erfolgsseite nach Zahlung
  GET  /billing/cancel        — Abbrechen-Seite
  POST /billing/portal        — Stripe Customer Portal (Verwaltung/Kündigung)
  POST /billing/webhook       — Stripe Webhook (CSRF-befreit)

Stripe Webhook-Events:
  checkout.session.completed      → Abo-Start, Company aktivieren
  invoice.payment_succeeded       → Monatliche Zahlung, SubscriptionPayment anlegen
  invoice.payment_failed          → Zahlung fehlgeschlagen, Company-Status → SUSPENDED
  customer.subscription.deleted   → Kündigung, Company-Status → CANCELLED
  customer.subscription.updated   → Planänderung (für spätere Nutzung)
"""
import logging
from datetime import datetime, date
from decimal import Decimal

import stripe
from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Company, SubscriptionPayment
from app.utils.auth import admin_required, log_action

logger = logging.getLogger(__name__)

billing_bp = Blueprint('billing', __name__)


def _stripe():
    """Return configured stripe module (reads key from app config)."""
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    return stripe


# ─── Billing-Übersicht ────────────────────────────────────────

@billing_bp.route('/billing/')
@login_required
@admin_required
def index():
    company = Company.query.get_or_404(current_user.company_id)
    payments = (SubscriptionPayment.query
                .filter_by(company_id=company.id)
                .order_by(SubscriptionPayment.period_start.desc())
                .limit(12).all())

    plan_name       = current_app.config.get('STRIPE_PLAN_NAME', 'PflegeOS Professional')
    plan_amount     = current_app.config.get('STRIPE_PLAN_AMOUNT', 25000) / 100
    plan_currency   = current_app.config.get('STRIPE_PLAN_CURRENCY', 'eur').upper()
    publishable_key = current_app.config.get('STRIPE_PUBLISHABLE_KEY', '')

    return render_template('billing/index.html',
                           company=company,
                           payments=payments,
                           plan_name=plan_name,
                           plan_amount=plan_amount,
                           plan_currency=plan_currency,
                           publishable_key=publishable_key)


# ─── Checkout starten ─────────────────────────────────────────

@billing_bp.route('/billing/checkout', methods=['POST'])
@login_required
@admin_required
def checkout():
    s = _stripe()
    company = Company.query.get_or_404(current_user.company_id)
    base_url = current_app.config.get('SYSTEM_URL') or request.host_url.rstrip('/')

    try:
        # Stripe Customer anlegen oder wiederverwenden
        if company.stripe_customer_id:
            customer_id = company.stripe_customer_id
        else:
            customer = s.Customer.create(
                email=company.email,
                name=company.name,
                metadata={'company_id': company.id, 'company_slug': company.slug or ''},
            )
            customer_id = customer.id
            company.stripe_customer_id = customer_id
            db.session.commit()

        # Checkout Session
        checkout_session = s.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': current_app.config['STRIPE_PRICE_ID'],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{base_url}{url_for('billing.success')}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}{url_for('billing.cancel')}",
            metadata={'company_id': company.id},
            subscription_data={
                'metadata': {'company_id': company.id},
            },
            locale='de',
        )

        log_action('STRIPE_CHECKOUT_STARTED', 'Company', company.id,
                   new_values={'session_id': checkout_session.id})

        return redirect(checkout_session.url, code=303)

    except stripe.StripeError as e:
        logger.error('Stripe checkout error: %s', e)
        flash(f'Stripe-Fehler: {e.user_message or str(e)}', 'danger')
        return redirect(url_for('billing.index'))


# ─── Erfolg nach Checkout ────────────────────────────────────

@billing_bp.route('/billing/success')
@login_required
def success():
    session_id = request.args.get('session_id', '')
    return render_template('billing/success.html', session_id=session_id)


# ─── Abbrechen ───────────────────────────────────────────────

@billing_bp.route('/billing/cancel')
@login_required
def cancel():
    flash('Checkout abgebrochen. Ihr Abo ist noch nicht aktiv.', 'warning')
    return redirect(url_for('billing.index'))


# ─── Onboarding: direkt nach Registrierung ───────────────────

@billing_bp.route('/billing/onboarding')
@login_required
@admin_required
def onboarding():
    """Erstellt sofort eine Stripe-Checkout-Session und leitet weiter (kein Formular nötig)."""
    s = _stripe()
    company = Company.query.get_or_404(current_user.company_id)
    base_url = current_app.config.get('SYSTEM_URL') or request.host_url.rstrip('/')

    try:
        if company.stripe_customer_id:
            customer_id = company.stripe_customer_id
        else:
            customer = s.Customer.create(
                email=company.email,
                name=company.name,
                metadata={'company_id': company.id, 'company_slug': company.slug or ''},
            )
            customer_id = customer.id
            company.stripe_customer_id = customer_id
            db.session.commit()

        checkout_session = s.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': current_app.config['STRIPE_PRICE_ID'],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{base_url}{url_for('billing.success')}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}{url_for('billing.cancel')}",
            metadata={'company_id': company.id},
            subscription_data={'metadata': {'company_id': company.id}},
            locale='de',
        )

        log_action('STRIPE_ONBOARDING_STARTED', 'Company', company.id)
        return redirect(checkout_session.url, code=303)

    except stripe.StripeError as e:
        logger.error('Stripe onboarding error: %s', e)
        flash(f'Stripe-Fehler: {e.user_message or str(e)}', 'danger')
        return redirect(url_for('dashboard.index'))


# ─── Stripe Customer Portal ──────────────────────────────────

@billing_bp.route('/billing/portal', methods=['POST'])
@login_required
@admin_required
def portal():
    s = _stripe()
    company = Company.query.get_or_404(current_user.company_id)
    base_url = current_app.config.get('SYSTEM_URL') or request.host_url.rstrip('/')

    if not company.stripe_customer_id:
        flash('Kein aktives Abonnement vorhanden.', 'warning')
        return redirect(url_for('billing.index'))

    try:
        portal_session = s.billing_portal.Session.create(
            customer=company.stripe_customer_id,
            return_url=f"{base_url}{url_for('billing.index')}",
        )
        return redirect(portal_session.url, code=303)
    except stripe.StripeError as e:
        logger.error('Stripe portal error: %s', e)
        flash(f'Stripe-Fehler: {e.user_message or str(e)}', 'danger')
        return redirect(url_for('billing.index'))


# ─── Webhook ─────────────────────────────────────────────────

@billing_bp.route('/billing/webhook', methods=['POST'])
def webhook():
    """Stripe sendet alle Events hierher. CSRF-exempt durch expliziten Eintrag in __init__.py."""
    s = _stripe()
    payload   = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')
    webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']

    try:
        event = s.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.errors.SignatureVerificationError as e:
        logger.warning('Stripe webhook signature invalid: %s', e)
        return 'Ungültige Signatur', 400
    except Exception as e:
        logger.error('Stripe webhook error: %s', e)
        return 'Fehler', 400

    _handle_event(event)
    return 'OK', 200


def _handle_event(event):
    """Dispatch Stripe events to handlers."""
    handlers = {
        'checkout.session.completed':    _on_checkout_completed,
        'invoice.payment_succeeded':     _on_invoice_paid,
        'invoice.payment_failed':        _on_invoice_failed,
        'customer.subscription.deleted': _on_subscription_cancelled,
        'customer.subscription.updated': _on_subscription_updated,
    }
    handler = handlers.get(event['type'])
    if handler:
        try:
            handler(event['data']['object'])
        except Exception as e:
            logger.error('Error handling Stripe event %s: %s', event['type'], e)
            db.session.rollback()


# ── Event-Handler ─────────────────────────────────────────────

def _get_company_by_customer(customer_id: str):
    return Company.query.filter_by(stripe_customer_id=customer_id, deleted_at=None).first()


def _get_company_by_metadata(obj) -> Company | None:
    """Try metadata first, then customer lookup."""
    company_id = (obj.get('metadata') or {}).get('company_id')
    if company_id:
        return Company.query.filter_by(id=company_id, deleted_at=None).first()
    customer_id = obj.get('customer')
    if customer_id:
        return _get_company_by_customer(customer_id)
    return None


def _on_checkout_completed(session_obj):
    """checkout.session.completed — Abo gestartet."""
    company = _get_company_by_metadata(session_obj)
    if not company:
        logger.warning('checkout.session.completed: company not found. session=%s', session_obj.get('id'))
        return

    sub_id = session_obj.get('subscription')
    company.stripe_subscription_id = sub_id
    company.status = 'ACTIVE'
    company.plan   = 'AKTIV'

    # Abo-Details laden um period_end zu kennen
    if sub_id:
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            company.subscription_status = sub['status']
            company.current_period_end  = datetime.fromtimestamp(sub['current_period_end'])
        except Exception as e:
            logger.warning('Could not retrieve subscription %s: %s', sub_id, e)

    db.session.commit()
    logger.info('Company %s activated via Stripe checkout.', company.id)


def _on_invoice_paid(invoice):
    """invoice.payment_succeeded — Monatliche Zahlung erfolgreich."""
    company = _get_company_by_metadata(invoice)
    if not company:
        # Try via subscription metadata
        sub_id = invoice.get('subscription')
        if sub_id:
            company = Company.query.filter_by(stripe_subscription_id=sub_id, deleted_at=None).first()
    if not company:
        logger.warning('invoice.payment_succeeded: company not found. invoice=%s', invoice.get('id'))
        return

    # Betrag in Euro
    amount_paid = Decimal(invoice.get('amount_paid', 0)) / 100
    currency    = (invoice.get('currency') or 'eur').upper()
    period_start = datetime.fromtimestamp(invoice['lines']['data'][0]['period']['start']).date()
    period_end   = datetime.fromtimestamp(invoice['lines']['data'][0]['period']['end']).date()

    # Company aktivieren / period_end aktualisieren
    company.status              = 'ACTIVE'
    company.subscription_status = 'active'
    company.current_period_end  = datetime.fromtimestamp(invoice['lines']['data'][0]['period']['end'])

    # SubscriptionPayment anlegen (nur wenn noch nicht vorhanden)
    existing = SubscriptionPayment.query.filter_by(
        stripe_invoice_id=invoice['id']
    ).first()
    if not existing:
        pmt = SubscriptionPayment(
            company_id=company.id,
            plan='AKTIV',
            betrag=amount_paid,
            waehrung=currency,
            period_start=period_start,
            period_end=period_end,
            status='PAID',
            payment_method='STRIPE',
            payment_ref=invoice.get('charge') or invoice.get('payment_intent'),
            stripe_invoice_id=invoice['id'],
            stripe_subscription_id=invoice.get('subscription'),
            paid_at=datetime.utcnow(),
        )
        db.session.add(pmt)

    db.session.commit()
    logger.info('Invoice paid for company %s: %s %s', company.id, amount_paid, currency)


def _on_invoice_failed(invoice):
    """invoice.payment_failed — Zahlung fehlgeschlagen."""
    company = _get_company_by_metadata(invoice)
    if not company:
        sub_id = invoice.get('subscription')
        if sub_id:
            company = Company.query.filter_by(stripe_subscription_id=sub_id, deleted_at=None).first()
    if not company:
        return

    company.subscription_status = 'past_due'
    # Erst nach Stripe-Retry-Periode suspendieren (Stripe versucht 3× erneut)
    # Hier setzen wir nur SUSPENDED wenn attempt_count hoch ist
    if invoice.get('attempt_count', 1) >= 3:
        company.status = 'SUSPENDED'

    # Fehlgeschlagene Zahlung vermerken
    existing = SubscriptionPayment.query.filter_by(
        stripe_invoice_id=invoice['id']
    ).first()
    if not existing:
        amount = Decimal(invoice.get('amount_due', 0)) / 100
        pmt = SubscriptionPayment(
            company_id=company.id,
            plan='AKTIV',
            betrag=amount,
            waehrung=(invoice.get('currency') or 'eur').upper(),
            period_start=date.today(),
            period_end=date.today(),
            status='FAILED',
            payment_method='STRIPE',
            stripe_invoice_id=invoice['id'],
            stripe_subscription_id=invoice.get('subscription'),
        )
        db.session.add(pmt)

    db.session.commit()
    logger.warning('Invoice payment failed for company %s', company.id)


def _on_subscription_cancelled(subscription):
    """customer.subscription.deleted — Kündigung."""
    company = Company.query.filter_by(
        stripe_subscription_id=subscription['id'], deleted_at=None
    ).first()
    if not company:
        company = _get_company_by_customer(subscription.get('customer', ''))
    if not company:
        return

    company.status               = 'CANCELLED'
    company.subscription_status  = 'canceled'
    company.stripe_subscription_id = None
    db.session.commit()
    logger.info('Subscription cancelled for company %s', company.id)


def _on_subscription_updated(subscription):
    """customer.subscription.updated — Status-Sync."""
    company = Company.query.filter_by(
        stripe_subscription_id=subscription['id'], deleted_at=None
    ).first()
    if not company:
        return

    company.subscription_status = subscription['status']
    company.current_period_end  = datetime.fromtimestamp(subscription['current_period_end'])

    if subscription['status'] == 'active':
        company.status = 'ACTIVE'
    elif subscription['status'] == 'past_due':
        pass  # Warten auf invoice.payment_failed
    elif subscription['status'] in ('canceled', 'unpaid'):
        company.status = 'CANCELLED'

    db.session.commit()
