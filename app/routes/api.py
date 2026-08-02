"""JSON API for Shortcuts / external clients (Bearer token auth)."""
from datetime import datetime, date

from flask import Blueprint, jsonify, request, g

from app.extensions import db, csrf, limiter
from app.security import api_token_required, clamp_text, safe_float, safe_int
from app.models import Todo, Transaction, Account, CADENCE_CHOICES
from app.services.sms_parse import parse_sms
from app.services.categories import ensure_category

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

csrf.exempt(api_bp)

VALID_CADENCE = {c[0] for c in CADENCE_CHOICES}


def _todo_json(t: Todo) -> dict:
    return {
        'id': t.id,
        'title': t.title,
        'notes': t.notes or '',
        'cadence': t.cadence,
        'cadence_label': t.cadence_label(),
        'cadence_day': t.cadence_day,
        'next_due': t.next_due.isoformat() if t.next_due else None,
        'status': t.status,
    }


def _tx_json(tx: Transaction) -> dict:
    return {
        'id': tx.id,
        'description': tx.description,
        'amount': tx.amount,
        'type': tx.type,
        'status': tx.status,
        'category': tx.category,
        'due_date': tx.due_date.isoformat() if tx.due_date else None,
        'account_id': tx.account_id,
    }


@api_bp.route('/me', methods=['GET'])
@api_token_required
@limiter.limit('60 per minute')
def me():
    u = g.api_user
    return jsonify({
        'id': u.id,
        'username': u.username,
        'email': u.email,
    })


@api_bp.route('/todos', methods=['GET'])
@api_token_required
@limiter.limit('60 per minute')
def list_todos():
    status = (request.args.get('status') or 'open').strip()
    q = Todo.query.filter_by(user_id=g.api_user.id)
    if status in ('open', 'done'):
        q = q.filter_by(status=status)
    items = q.order_by(Todo.next_due.asc()).limit(100).all()
    return jsonify({'todos': [_todo_json(t) for t in items]})


@api_bp.route('/todos', methods=['POST'])
@api_token_required
@limiter.limit('30 per minute')
def create_todo():
    data = request.get_json(silent=True) or {}
    title = clamp_text(data.get('title'), 200)
    if not title:
        return jsonify({'error': 'validation', 'message': 'title is required'}), 400
    notes = clamp_text(data.get('notes'), 500)
    cadence = (data.get('cadence') or 'once').strip()
    if cadence not in VALID_CADENCE:
        cadence = 'once'
    next_due = None
    due_str = data.get('next_due')
    if due_str:
        try:
            next_due = datetime.strptime(str(due_str)[:10], '%Y-%m-%d').date()
        except ValueError:
            pass
    if next_due is None:
        next_due = date.today()
    cadence_day = None
    if cadence == 'weekly':
        cadence_day = safe_int(data.get('cadence_day'), next_due.weekday(), 0, 6)
    elif cadence == 'monthly':
        cadence_day = safe_int(data.get('cadence_day'), min(next_due.day, 28), 1, 28)
    todo = Todo(
        title=title,
        notes=notes,
        cadence=cadence,
        cadence_day=cadence_day,
        next_due=next_due,
        status='open',
        user_id=g.api_user.id,
    )
    db.session.add(todo)
    db.session.commit()
    return jsonify({'todo': _todo_json(todo)}), 201


@api_bp.route('/todos/<int:todo_id>/complete', methods=['POST'])
@api_token_required
@limiter.limit('30 per minute')
def complete_todo(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=g.api_user.id).first()
    if not todo:
        return jsonify({'error': 'not_found'}), 404
    if todo.status != 'open':
        return jsonify({'todo': _todo_json(todo), 'message': 'already done'})
    if (todo.cadence or 'once') == 'once':
        todo.status = 'done'
    else:
        todo.advance_next_due(from_date=max(todo.next_due, date.today()))
    db.session.commit()
    return jsonify({'todo': _todo_json(todo)})


@api_bp.route('/pending', methods=['GET'])
@api_token_required
@limiter.limit('60 per minute')
def list_pending():
    items = (
        Transaction.query.filter_by(user_id=g.api_user.id, status='pending')
        .order_by(Transaction.due_date.asc().nullslast())
        .limit(100)
        .all()
    )
    return jsonify({'pending': [_tx_json(t) for t in items]})


@api_bp.route('/pending', methods=['POST'])
@api_token_required
@limiter.limit('30 per minute')
def create_pending():
    data = request.get_json(silent=True) or {}
    description = clamp_text(data.get('description'), 200)
    amount = safe_float(data.get('amount'), 0.0, 0.01, 1e12)
    if not description:
        return jsonify({'error': 'validation', 'message': 'description is required'}), 400
    if amount <= 0:
        return jsonify({'error': 'validation', 'message': 'amount must be positive'}), 400
    accounts = Account.query.filter_by(user_id=g.api_user.id).all()
    if not accounts:
        return jsonify({'error': 'validation', 'message': 'create an account first'}), 400
    account_id = safe_int(data.get('account_id'), accounts[0].id)
    account = Account.query.filter_by(id=account_id, user_id=g.api_user.id).first()
    if not account:
        return jsonify({'error': 'validation', 'message': 'invalid account_id'}), 400
    due_date = None
    if data.get('due_date'):
        try:
            due_date = datetime.strptime(str(data['due_date'])[:10], '%Y-%m-%d').date()
        except ValueError:
            pass
    category = clamp_text(data.get('category'), 50) or 'General'
    tx = Transaction(
        description=description,
        amount=amount,
        type='expense',
        status='pending',
        category=category,
        due_date=due_date,
        account_id=account.id,
        user_id=g.api_user.id,
    )
    db.session.add(tx)
    db.session.commit()
    return jsonify({'transaction': _tx_json(tx)}), 201


@api_bp.route('/accounts', methods=['GET'])
@api_token_required
@limiter.limit('60 per minute')
def list_accounts():
    accounts = Account.query.filter_by(user_id=g.api_user.id).all()
    return jsonify({
        'accounts': [
            {
                'id': a.id,
                'name': a.name,
                'account_type': a.account_type,
                'balance': a.balance,
            }
            for a in accounts
        ]
    })


@api_bp.route('/sms-transaction', methods=['POST'])
@api_token_required
@limiter.limit('60 per minute')
def sms_transaction():
    """Ingest an SMS (from iOS Shortcuts) and create a completed transaction.

    Accepts JSON or form fields:
      - text / body / message  (required) — full SMS body
      - sender                (optional) — SMS sender id
      - account_id            (optional) — override account
      - status                (optional) — completed (default) | pending
      - dry_run               (optional) — if true, only return parse result

    Updates account balance when status is completed.
    """
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict() if request.form else {}

    text = (
        data.get('text')
        or data.get('body')
        or data.get('message')
        or data.get('sms')
        or ''
    )
    text = clamp_text(str(text), 2000)
    sender = clamp_text(str(data.get('sender') or data.get('from') or ''), 80) or None

    parsed = parse_sms(text, sender=sender)
    if not parsed:
        return jsonify({
            'error': 'parse_failed',
            'message': 'Could not extract amount from SMS. Send the full message text.',
            'received_preview': text[:200],
        }), 422

    dry_run = str(data.get('dry_run') or '').lower() in ('1', 'true', 'yes')
    if dry_run:
        return jsonify({'parsed': parsed.to_dict(), 'dry_run': True})

    accounts = Account.query.filter_by(user_id=g.api_user.id).order_by(Account.id).all()
    if not accounts:
        return jsonify({'error': 'no_account', 'message': 'Create a bank/cash account first'}), 400

    account = None
    account_id = data.get('account_id')
    if account_id is not None and str(account_id).strip() != '':
        account = Account.query.filter_by(
            id=safe_int(account_id), user_id=g.api_user.id
        ).first()
        if not account:
            return jsonify({'error': 'validation', 'message': 'invalid account_id'}), 400
    elif parsed.account_hint:
        hint = parsed.account_hint
        for a in accounts:
            if hint in (a.name or ''):
                account = a
                break
    if account is None:
        account = accounts[0]

    status = (data.get('status') or 'completed').strip().lower()
    if status not in ('completed', 'pending'):
        status = 'completed'

    category = ensure_category(g.api_user.id, parsed.category)

    tx = Transaction(
        description=parsed.description,
        amount=parsed.amount,
        type=parsed.tx_type,
        status=status,
        category=category,
        account_id=account.id,
        user_id=g.api_user.id,
        date=datetime.utcnow(),
    )
    db.session.add(tx)

    if status == 'completed':
        if parsed.tx_type == 'expense':
            account.balance = (account.balance or 0) - parsed.amount
        else:
            account.balance = (account.balance or 0) + parsed.amount

    db.session.commit()

    return jsonify({
        'ok': True,
        'parsed': parsed.to_dict(),
        'transaction': _tx_json(tx),
        'account': {
            'id': account.id,
            'name': account.name,
            'balance': account.balance,
        },
    }), 201
