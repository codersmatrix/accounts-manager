"""Budgets and category reports."""
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Budget
from app.security import clamp_text, safe_float, safe_int, require_owner
from app.services.categories import list_categories, ensure_category
from app.services.reports import category_spend, category_income, budget_progress, monthly_trend

budgets_bp = Blueprint('budgets', __name__)


def _period_from_request():
    today = date.today()
    year = safe_int(request.args.get('year') or request.form.get('year'), today.year, 2000, 2100)
    month = safe_int(request.args.get('month') or request.form.get('month'), today.month, 1, 12)
    return year, month


@budgets_bp.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():
    year, month = _period_from_request()
    if request.method == 'POST':
        action = request.form.get('action') or 'save'
        if action == 'delete':
            bid = safe_int(request.form.get('budget_id'), 0)
            b = Budget.query.get(bid)
            require_owner(b)
            db.session.delete(b)
            db.session.commit()
            flash('Budget removed.', 'info')
            return redirect(url_for('budgets.budgets', year=year, month=month))

        category = clamp_text(request.form.get('category'), 50) or 'General'
        amount = safe_float(request.form.get('amount'), 0, min_v=0)
        notes = clamp_text(request.form.get('notes'), 200) or None
        y = safe_int(request.form.get('year'), year, 2000, 2100)
        m = safe_int(request.form.get('month'), month, 1, 12)
        if amount <= 0:
            flash('Budget amount must be greater than zero.', 'warning')
            return redirect(url_for('budgets.budgets', year=y, month=m))
        ensure_category(current_user.id, category)
        existing = Budget.query.filter_by(
            user_id=current_user.id, category=category, year=y, month=m
        ).first()
        if existing:
            existing.amount = amount
            existing.notes = notes
            flash(f'Updated budget for {category}.', 'success')
        else:
            db.session.add(Budget(
                user_id=current_user.id,
                category=category,
                amount=amount,
                year=y,
                month=m,
                notes=notes,
            ))
            flash(f'Budget set for {category}.', 'success')
        db.session.commit()
        return redirect(url_for('budgets.budgets', year=y, month=m))

    rows = budget_progress(current_user.id, year, month)
    cats = list_categories(current_user.id)
    total_budget = sum(r['budget'] for r in rows if r.get('budget'))
    total_spent = sum(r['spent'] for r in rows)
    return render_template(
        'budgets.html',
        rows=rows,
        year=year,
        month=month,
        categories=cats,
        total_budget=total_budget,
        total_spent=total_spent,
        months=list(range(1, 13)),
    )


@budgets_bp.route('/reports')
@login_required
def reports():
    year, month = _period_from_request()
    exp = category_spend(current_user.id, year, month)
    inc = category_income(current_user.id, year, month)
    progress = budget_progress(current_user.id, year, month)
    exp_items = sorted(exp['by_category'].items(), key=lambda x: -x[1])
    inc_items = sorted(inc['by_category'].items(), key=lambda x: -x[1])
    max_exp = max((v for _, v in exp_items), default=1) or 1
    trend = monthly_trend(current_user.id, year, month, months_back=6)
    return render_template(
        'reports.html',
        year=year,
        month=month,
        expense_total=exp['total'],
        income_total=inc['total'],
        net=inc['total'] - exp['total'],
        exp_items=exp_items,
        inc_items=inc_items,
        max_exp=max_exp,
        progress=progress,
        expense_count=exp['count'],
        income_count=inc['count'],
        months=list(range(1, 13)),
        trend=trend,
        chart_exp_labels=[c for c, _ in exp_items[:12]],
        chart_exp_values=[round(v, 2) for _, v in exp_items[:12]],
        chart_inc_labels=[c for c, _ in inc_items[:12]],
        chart_inc_values=[round(v, 2) for _, v in inc_items[:12]],
        chart_trend_labels=[t['label'] for t in trend],
        chart_trend_income=[t['income'] for t in trend],
        chart_trend_expense=[t['expense'] for t in trend],
        chart_trend_net=[t['net'] for t in trend],
    )
