from datetime import datetime, date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.security import require_owner, clamp_text, safe_int
from app.models import Todo, CADENCE_CHOICES
from app.services.email import is_mail_configured, send_email

todos_bp = Blueprint('todos', __name__)

VALID_CADENCE = {c[0] for c in CADENCE_CHOICES}
WEEKDAYS = [
    (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
    (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
]


def _parse_todo_form(form, existing=None):
    title = clamp_text(form.get('title'), 200)
    notes = clamp_text(form.get('notes'), 500)
    cadence = form.get('cadence', 'once')
    if cadence not in VALID_CADENCE:
        cadence = 'once'
    due_str = form.get('next_due')
    next_due = None
    if due_str:
        try:
            next_due = datetime.strptime(due_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if next_due is None:
        next_due = existing.next_due if existing else date.today()
    cadence_day = None
    if cadence == 'weekly':
        cadence_day = safe_int(form.get('cadence_day'), next_due.weekday(), 0, 6)
    elif cadence == 'monthly':
        cadence_day = safe_int(form.get('cadence_day'), min(next_due.day, 28), 1, 28)
    return title, notes, cadence, cadence_day, next_due


@todos_bp.route('/todos')
@login_required
def todos():
    open_items = (
        Todo.query.filter_by(user_id=current_user.id, status='open')
        .order_by(Todo.next_due.asc(), Todo.title)
        .all()
    )
    done_items = (
        Todo.query.filter_by(user_id=current_user.id, status='done')
        .order_by(Todo.next_due.desc())
        .limit(20)
        .all()
    )
    today = date.today()
    due_today = [t for t in open_items if t.next_due <= today]
    return render_template(
        'todos.html',
        open_items=open_items,
        done_items=done_items,
        due_today=due_today,
        today=today,
        mail_configured=is_mail_configured(),
    )


@todos_bp.route('/todos/add', methods=['GET', 'POST'])
@login_required
def add_todo():
    if request.method == 'POST':
        title, notes, cadence, cadence_day, next_due = _parse_todo_form(request.form)
        if not title:
            flash('Title is required.', 'danger')
            return redirect(url_for('todos.add_todo'))
        todo = Todo(
            title=title,
            notes=notes,
            cadence=cadence,
            cadence_day=cadence_day,
            next_due=next_due,
            status='open',
            user_id=current_user.id,
        )
        db.session.add(todo)
        db.session.commit()
        flash(f'Reminder "{title}" added.', 'success')
        return redirect(url_for('todos.todos'))
    return render_template(
        'add_todo.html',
        cadences=CADENCE_CHOICES,
        weekdays=WEEKDAYS,
        today=date.today().isoformat(),
    )


@todos_bp.route('/todos/<int:todo_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_todo(todo_id):
    todo = require_owner(Todo.query.get(todo_id))
    if request.method == 'POST':
        title, notes, cadence, cadence_day, next_due = _parse_todo_form(request.form, todo)
        if not title:
            flash('Title is required.', 'danger')
            return redirect(url_for('todos.edit_todo', todo_id=todo.id))
        todo.title = title
        todo.notes = notes
        todo.cadence = cadence
        todo.cadence_day = cadence_day
        todo.next_due = next_due
        status = request.form.get('status')
        if status in ('open', 'done'):
            todo.status = status
        db.session.commit()
        flash('Reminder updated.', 'success')
        return redirect(url_for('todos.todos'))
    return render_template(
        'edit_todo.html',
        todo=todo,
        cadences=CADENCE_CHOICES,
        weekdays=WEEKDAYS,
    )


@todos_bp.route('/todos/<int:todo_id>/complete', methods=['POST'])
@login_required
def complete_todo(todo_id):
    todo = require_owner(Todo.query.get(todo_id))
    if todo.status != 'open':
        flash('Already done.', 'info')
        return redirect(request.referrer or url_for('todos.todos'))
    if (todo.cadence or 'once') == 'once':
        todo.status = 'done'
        flash(f'Completed: {todo.title}', 'success')
    else:
        todo.advance_next_due(from_date=max(todo.next_due, date.today()))
        flash(
            f'Completed for this period. Next: {todo.next_due.strftime("%d %b %Y")} ({todo.cadence_label()})',
            'success',
        )
    db.session.commit()
    return redirect(request.referrer or url_for('todos.todos'))


@todos_bp.route('/todos/<int:todo_id>/delete', methods=['POST'])
@login_required
def delete_todo(todo_id):
    todo = require_owner(Todo.query.get(todo_id))
    db.session.delete(todo)
    db.session.commit()
    flash('Reminder deleted.', 'success')
    return redirect(url_for('todos.todos'))


@todos_bp.route('/todos/send_reminders', methods=['POST'])
@login_required
@limiter.limit('5 per hour')
def send_todo_reminders():
    if not current_user.email:
        flash('Set your email in Settings first.', 'warning')
        return redirect(url_for('settings.settings'))
    if not is_mail_configured():
        flash('Configure SMTP in environment / Settings first.', 'warning')
        return redirect(url_for('todos.todos'))
    today = date.today()
    due = (
        Todo.query.filter_by(user_id=current_user.id, status='open')
        .filter(Todo.next_due <= today)
        .order_by(Todo.next_due.asc())
        .all()
    )
    if not due:
        flash('No due reminders to send.', 'info')
        return redirect(url_for('todos.todos'))
    lines_html = []
    lines_text = []
    for t in due:
        flag = 'OVERDUE' if t.next_due < today else 'TODAY'
        lines_html.append(
            f'<li><strong>{t.title}</strong> — {t.next_due.strftime("%d %b %Y")} '
            f'({t.cadence_label()}, {flag})'
            + (f'<br><small>{t.notes}</small>' if t.notes else '')
            + '</li>'
        )
        lines_text.append(f'- {t.title} | {t.next_due} | {t.cadence_label()} | {flag}')
    subject = f'[Accounts Manager] {len(due)} reminder(s) due'
    html = (
        f'<p>Hi {current_user.username},</p>'
        f'<p>You have <strong>{len(due)}</strong> todo reminder(s) due:</p>'
        f'<ul>{("".join(lines_html))}</ul>'
        f'<p>Open the app → Todos to complete them.</p>'
    )
    text = f'Hi {current_user.username},\n\nDue reminders:\n' + '\n'.join(lines_text)
    ok, err = send_email(current_user.email, subject, html, text)
    if ok:
        now = datetime.utcnow()
        for t in due:
            t.last_reminded_at = now
        db.session.commit()
        flash(f'Reminders emailed for {len(due)} item(s).', 'success')
    else:
        flash(f'Failed to send email: {err}', 'danger')
    return redirect(url_for('todos.todos'))
