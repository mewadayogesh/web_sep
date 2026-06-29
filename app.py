import csv
from flask import Response, Flask, render_template, request, redirect, url_for, session
import io
from flask_sqlalchemy import SQLAlchemy
from collections import Counter
import json
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = '@2005'  # Required for session

#vercel
# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False                
db = SQLAlchemy(app)


# ── User  & roles ─────────────────────────────────────────────────────────────────
# Role "admin"  → full access (edit, delete, task visible)
# Role "editor" → edit + delete, task visible  (username: abc)              
# Role "viewer" → read-only, task hidden        (username: user, ravi)

USERS = {
    "admin":  {"password": "admin123", "role": "admin"},
    "abc":    {"password": "abc123",    "role": "editor"},
    "user":   {"password": "user123",  "role": "viewer"},   # ← read-only user
    "ravi":   {"password": "ravi123",  "role": "viewer"},   # ← read-only user
    "raj":    {"password":"raj123","role":"viewer"},
    "ramu":   {"password":"ramu123","role":"viewer"}
}


# function for users data 
def current_role():
    return USERS.get(session.get('username', ''), {}).get('role', '')

def can_see_task():
    """admin and editor can see the Task field; viewer cannot."""
    return current_role() in ('admin', 'editor')

def can_edit():
    """Only admin and editor may edit, delete, or create records."""
    return current_role() in ('admin', 'editor')

def login_required(f):
    """Decorator to protect routes from unauthenticated access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


# ── Database Table Model ──────────────────────────────────────────────────────
class DDEntry(db.Model):
    id             = db.Column(db.Integer, primary_key=True)    #serial number given by this
    department     = db.Column(db.String(100))                
    work           = db.Column(db.String(100))
    date           = db.Column(db.String(50))
    Global         = db.Column(db.String(50))
    purpose        = db.Column(db.String(100))
    material       = db.Column(db.String(100))
    other_material = db.Column(db.String(100))
    item_type      = db.Column(db.String(100))
    other_type     = db.Column(db.String(100))
    frequency      = db.Column(db.String(100))
    quantity       = db.Column(db.String(100))
    project        = db.Column(db.String(200))
    description    = db.Column(db.Text)                         #no limit of data to save
    priority       = db.Column(db.String(100))
    item           = db.Column(db.String(100))
    task           = db.Column(db.String(100))


# ── Shared sidebar + layout helpers ────────────────────────────────────────────────────────────────────────────────────────────────────────

SIDEBAR_CSS = """
* { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',Arial,sans-serif; }
body { background:linear-gradient(135deg,#eef2ff,#dbeafe); color:#1f2937; overflow-x:hidden; }
.wrapper { display:flex; min-height:100vh; }
.sidebar {
    position:fixed; top:0; left:0; width:220px; height:100vh;
    background:linear-gradient(180deg,#1e3a8a,lightgreen);
    color:white; padding-top:20px;
    box-shadow:4px 0 15px rgba(0,0,0,0.15); z-index:1000;
}
.sidebar .brand {
    text-align:center; font-size:22px; font-weight:700;
    color:white; padding:0 10px 24px; border-bottom:1px solid rgba(255,255,255,0.2);
    margin-bottom:10px;
}
.sidebar ul { list-style:none; }
.sidebar ul li a {
    display:block; padding:14px 20px; color:white;
    text-decoration:none; font-size:14px; transition:.25s;
}
.sidebar ul li a:hover {
    background:rgba(255,255,255,.15);
    border-left:4px solid white; padding-left:25px;
}
.sidebar ul li a.active {
    background:rgba(255,255,255,.2);
    border-left:4px solid white; padding-left:25px; font-weight:600;
}

.content { margin-left:240px; padding:28px; width:calc(100% - 240px); min-height:100vh; overflow-x:auto; }
@media(max-width:768px){
    .sidebar{width:160px;}
    .content{margin-left:180px;width:calc(100% - 180px);padding:15px;}
}
"""

def sidebar_html(active=""):
    links = [
        ("/dashboards", "🏠 Dashboard",     "dashboard"),
        ("/dashboard", "📝 New Entry",     "new_entry"),
        ("/master",    "🔍 Master Tracker","master"),
        ("/records",   "📊 Reports",        "records"),
        ("/logout",    "🚪 Logout",         "logout"),
    ]
    items = ""
    for href, label, key in links:
        # HIDE "New Entry" form link if the user has a viewer profile
        if key == "new_entry" and not can_edit():
            continue
            
        cls = ' class="active"' if key == active else ""
        items += f'<li><a href="{href}"{cls}>{label}</a></li>\n'
    return f"""
    <div class="sidebar">
        <div class="brand">D&amp;D Dept</div>
        <ul>{items}</ul>
    </div>"""

def page_shell(title, active, body_html, extra_css=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
    {SIDEBAR_CSS}
    {extra_css}
    </style>
</head>
<body>
<div class="wrapper">
    {sidebar_html(active)}
    <div class="content">
        {body_html}
    </div>
</div>
</body>
</html>"""


# ── CSV download ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
@app.route('/download/excel')
@login_required
def download_excel():
    records = DDEntry.query.all()
    output  = io.StringIO()
    writer  = csv.writer(output)

#header of th excel data.
    headers = [
        'S.No', 'Department', 'Work Type', 'Global ID','Date' , 'Purpose',
        'Material', 'Material (Other)', 'Type', 'Type (Other)',
        'Frequency', 'Quantity', 'Project Name', 'Description',
        'Priority', 'Item Status']
    if can_see_task():
        headers.append('Task')
    writer.writerow(headers)

# data downloading given the sequence number by this loop 
    for index, row in enumerate(records, start=1):
        data_row = [
            index,
            row.department, row.work,row.Global,row.date, row.purpose,
            row.material, row.other_material, row.item_type, row.other_type,
            row.frequency, row.quantity, row.project, row.description,
            row.priority, row.item
        ]
        if can_see_task():
            data_row.append(row.task)
        writer.writerow(data_row)

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=datareport.csv"}
    )


# ── Edit record ───────────────────────────────────────────────────────────────
#edit the records in master tracker search bar 
#get retrieve data and post create record also update records
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not can_edit():
        return redirect(url_for('records'))

    entry = DDEntry.query.get_or_404(id)

    if request.method == 'POST':
        entry.department     = request.form.get('department', '')
        entry.work           = request.form.get('work', '')
        entry.date           = request.form.get('date', '')
        entry.Global         = request.form.get('Global', '')
        entry.purpose        = request.form.get('purpose', '')
        entry.material       = request.form.get('material', '')
        entry.other_material = request.form.get('other_material', '')
        entry.item_type      = request.form.get('item_type', '')
        entry.other_type     = request.form.get('other_type', '')
        entry.frequency      = request.form.get('frequency', '')
        entry.quantity       = request.form.get('quantity', '')
        entry.project        = request.form.get('project', '')
        entry.description    = request.form.get('description', '')
        entry.priority       = request.form.get('priority', '')
        entry.item           = request.form.get('item', '')
        if can_see_task():
            entry.task = request.form.get('task', '')
        db.session.commit()
        return redirect(url_for('records'))

    task_field_html = ""
    if can_see_task():
        task_field_html = f"""
            <div class="form-group">
                <label>Task</label>
                <input type="text" name="task" value="{entry.task or ''}">
            </div>"""

    body = f"""
    <div class="form-card">
        <h2>Edit Record #{entry.id}</h2>
        <form method="POST">
            <div class="form-grid">
                <div class="form-group"><label>Department</label><input type="text" name="department" value="{entry.department or ''}"></div>
                <div class="form-group"><label>Work Type</label><input type="text" name="work" value="{entry.work or ''}"></div>
                <div class="form-group"><label>Date</label><input type="date" name="date" value="{entry.date or ''}"></div>
                <div class="form-group"><label>Global ID</label><input type="text" name="Global" value="{entry.Global or ''}"></div>
                <div class="form-group"><label>Purpose</label><input type="text" name="purpose" value="{entry.purpose or ''}"></div>
                <div class="form-group"><label>Material</label><input type="text" name="material" value="{entry.material or ''}"></div>
                <div class="form-group"><label>Material (Other)</label><input type="text" name="other_material" value="{entry.other_material or ''}"></div>
                <div class="form-group"><label>Type</label><input type="text" name="item_type" value="{entry.item_type or ''}"></div>
                <div class="form-group"><label>Type (Other)</label><input type="text" name="other_type" value="{entry.other_type or ''}"></div>
                <div class="form-group"><label>Frequency</label><input type="text" name="frequency" value="{entry.frequency or ''}"></div>
                <div class="form-group"><label>Quantity</label><input type="text" name="quantity" value="{entry.quantity or ''}"></div>
                <div class="form-group"><label>Priority</label><input type="text" name="priority" value="{entry.priority or ''}"></div>
                <div class="form-group"><label>Item Status</label><input type="text" name="item" value="{entry.item or ''}"></div>
                <div class="form-group full-width"><label>Project Name</label><input type="text" name="project" value="{entry.project or ''}"></div>
                <div class="form-group full-width"><label>Description</label><textarea name="description" rows="3">{entry.description or ''}</textarea></div>
                {task_field_html}
            </div>
            <button type="submit" class="btn-submit">Update Record</button>
            <a href="{url_for('records')}" class="btn-cancel">Cancel</a>
        </form>
    </div>"""

    extra_css = """
    .form-card { max-width:98%; margin:0 auto; background:lightblue; padding:20px; border-radius:12px; box-shadow:0 10px 15px -3px rgba(0,0,0,0.06); }
    h2 { margin-top:0; text-align:center; color:#1f2937; border-bottom:2px solid #f3f4f6; padding-bottom:15px; margin-bottom:8px; }
    
    <!--.form-grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; }-->
    
    .form-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:18px; }
    
    
    .form-group { display:flex; flex-direction:column; gap:6px; }
    .full-width { grid-column:span 2; }
    
    label { font-weight:600; font-size:14px; color:black; }
    input, textarea { width:100%; padding:10px 14px; border:1px solid black; border-radius:8px; box-sizing:border-box; font-size:14px; color:black; }
    input:focus, textarea:focus { outline:none; border-color:#3b82f6; box-shadow:0 0 0 3px rgba(59,130,246,0.12); }
    
    /* old code
    .btn-submit {background:#0284c7; color:white; border:none; padding:14px 20px; border-radius:8px; cursor:pointer; font-weight:bold; width:30%; margin-top:25px; font-size:15px; }
    .btn-submit:hover { background:#0369a1; }
    .btn-cancel { display:block; text-align:center; margin-top:15px; color:#64748b; text-decoration:none; font-size:14px; font-weight:500; }
    .btn-cancel:hover { color:#334155; }
    */
    
/* Submit Button */
.btn-submit{display:block;width:240px;margin:20px auto 0;padding:14px 25px;background:linear-gradient(135deg,#0284c7,#0369a1);color:#fff;border:none;border-radius:10px;font-size:15px;font-weight:600;letter-spacing:.5px;cursor:pointer;box-shadow:0 6px 15px rgba(2,132,199,.35);transition:all .3s ease;}
/*.btn-submit:hover{background:linear-gradient(135deg,#0369a1,#075985);    transform:translateY(-3px);box-shadow:0 10px 20px rgba(2,132,199,.45);}*/

.btn-submit:hover{background:lightgrey;    transform:translateY(-3px);box-shadow:0 10px 20px rgba(2,132,199,.45);}
.btn-submit:active{transform:scale(.97);}

/* Cancel Button */
.btn-cancel{display:block;width:240px;margin:10px auto 0;padding:12px 25px;text-align:center;background:#f8fafc;color:#0369a1;border:2px solid #0284c7;border-radius:10px;text-decoration:none;font-size:15px;font-weight:600;transition:all .3s ease;}
.btn-cancel:hover{background:#334155;    color:#fff;transform:translateY(-2px);box-shadow:0 8px 18px rgba(2,132,199,.3);}
.btn-cancel:active{transform:scale(.97);}
"""

    return page_shell(f"Edit Record #{entry.id}", "records", body, extra_css)


# ── Delete record ─────────────────────────────────────────────────────────────

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    if not can_edit():
        return redirect(url_for('records'))

    entry = DDEntry.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('records'))


# ── Login & Logout ────────────────────────────────────────────────────────────
@app.route('/')
def login_page():
    if 'username' in session:
        return redirect(url_for('records'))
    return render_template('login.html', error=None)

@app.route('/login', methods=['POST'])
def login_auth():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    user = USERS.get(username)
    if user and user['password'] == password:
        session['username'] = username
        # Viewers safely drop into the records view; admins/editors can choose
        if user['role'] == 'viewer':
            return redirect(url_for('records'))
        return redirect(url_for('dashboards'))

    return render_template('login.html', error="Invalid Username or Password")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# ── Dashboard entry data (New Entry Form Page) ────────────────────────────────

@app.route('/dashboard')
@login_required
def home():
    # If role is 'viewer', they cannot look at the submission entry page
    if not can_edit():
        return redirect(url_for('records'))
    return render_template('index.html')


# ── Dashboard Analytics ───────────────────────────────────────────────────────
"""
@app.route('/dashboards')
@login_required
def dashboards():
    records = DDEntry.query.all()
    total_records = len(records)

    dept_data = Counter([r.department for r in records if r.department])
    priority_data = Counter([r.priority for r in records if r.priority])
    
    # Calculate Task stats for the third chart
    task_data = Counter([r.task for r in records if r.task])

    return render_template(
        'dashboard.html',
        total_records=total_records,
        dept_labels=json.dumps(list(dept_data.keys())),
        dept_values=json.dumps(list(dept_data.values())),
        priority_labels=json.dumps(list(priority_data.keys())),
        priority_values=json.dumps(list(priority_data.values())),
        # New variables passed to frontend:
        task_labels=json.dumps(list(task_data.keys())),
        task_values=json.dumps(list(task_data.values())),
        can_see_task=can_see_task()  # cleaner than hardcoding usernames in HTML
    )
"""
#old code
@app.route('/dashboards')
@login_required
def dashboards():
    records = DDEntry.query.all()
    total_records = len(records)

    dept_data = Counter([r.department for r in records if r.department])
    priority_data = Counter([r.priority for r in records if r.priority])

    return render_template(
        'dashboard.html',
        total_records=total_records,
        dept_labels=json.dumps(list(dept_data.keys())),
        dept_values=json.dumps(list(dept_data.values())),
        priority_labels=json.dumps(list(priority_data.keys())),
        priority_values=json.dumps(list(priority_data.values()))
    )


# ── Save new entry ────────────────────────────────────────────────────────────
@app.route('/save', methods=['POST'])
@login_required
def save():
    if not can_edit():
        return redirect(url_for('records'))

    work_type = request.form.get('work', '')
    if work_type == "Mechanical Design Related":
        material = item_type = frequency =quantity= other_material = other_type = ""
        chosen_purpose  = request.form.get('purpose_mechanical', '')
        chosen_priority = request.form.get('priority_mechanical', '')
    else:
        material        = request.form.get('material', '')
        item_type       = request.form.get('item_type', '')
        frequency       = request.form.get('frequency', '')
        quantity        = request.form.get('quantity', '')
        other_material  = request.form.get('other_material', '')
        other_type      = request.form.get('other_type', '')
        chosen_purpose  = request.form.get('purpose_testing', '')
        chosen_priority = request.form.get('priority_testing', '')

    entry = DDEntry(
        department=request.form.get('department', ''),
        work=work_type,
        date=request.form.get('date', ''),
        Global=request.form.get('Global', ''),
        purpose=chosen_purpose,
        material=material, other_material=other_material,
        item_type=item_type, other_type=other_type,
        frequency=frequency, quantity=quantity,
        project=request.form.get('project', ''),
        description=request.form.get('description', ''),
        priority=chosen_priority,
        item=request.form.get('item', ''),
        task=request.form.get('task', '')
    )
    db.session.add(entry)
    db.session.commit()
    return redirect(url_for('records'))


# ── Master tracker ────────────────────────────────────────────────────────────
@app.route('/master')
@login_required
def master():
    unique_id     = request.args.get('Global', '').strip()
    entry         = None
    error_message = None

    if unique_id:
        entry = DDEntry.query.filter_by(Global=unique_id).first()
        if not entry:
            error_message = f"No record found with Global ID '{unique_id}'."

    task_detail_html = ""
    if entry and can_see_task():
        task_detail_html = f'<div class="detail-group"><span class="label">Task:</span> {entry.task or "N/A"}</div>'

    edit_btn_html = ""
    if entry and can_edit():
        edit_btn_html = f'<a href="/edit/{entry.id}" class="btn-edit">✏️ Edit This Record</a>'

    if entry:
        result_html = f"""
        <div class="result-card">
            <h3>Record Details: #{entry.id}</h3>
            <div class="detail-grid">
                <div class="detail-group"><span class="label">Department :</span> {entry.department or 'N/A'}</div>
                <div class="detail-group"><span class="label">Work Type :</span> {entry.work or 'N/A'}</div>
                <div class="detail-group"><span class="label">Date :</span> {entry.date or 'N/A'}</div>
                <div class="detail-group"><span class="label">Global ID :</span> {entry.Global or 'N/A'}</div>
                <div class="detail-group"><span class="label">Purpose :</span> {entry.purpose or 'N/A'}</div>
                <div class="detail-group"><span class="label">Material :</span> {entry.material or 'N/A'}</div>
                <div class="detail-group"><span class="label">Material (Other) :</span> {entry.other_material or 'N/A'}</div>
                <div class="detail-group"><span class="label">Type :</span> {entry.item_type or 'N/A'}</div>
                <div class="detail-group"><span class="label">Type (Other) :</span> {entry.other_type or 'N/A'}</div>
                <div class="detail-group"><span class="label">Frequency :</span> {entry.frequency or 'N/A'}</div>
                <div class="detail-group"><span class="label">Quantity :</span> {entry.quantity or 'N/A'}</div>
                <div class="detail-group"><span class="label">Priority :</span> <span class="badge">{entry.priority or 'N/A'}</span></div>
                <div class="detail-group"><span class="label">Item Status :</span> <span class="badge">{entry.item or 'N/A'}</span></div>
                <div class="detail-group full-width"><span class="label">Project Name :</span> {entry.project or 'N/A'}</div>
                <div class="detail-group full-width"><span class="label">Description :</span>
                    <p class="desc-text">{entry.description or 'No description provided.'}</p>
                </div>
                {task_detail_html}
            </div>
            <div class="actions">
                {edit_btn_html}
            </div>
        </div>"""
    elif error_message:
        result_html = f'<div class="alert alert-error">{error_message}</div>'
    else:
        result_html = '<div class=""></div>'

    body = f"""
    <div class="container">
        <h2 class="page-title">Master Records</h2>
        <div class="search-card">
            <label style="font-weight:600;font-size:20px;color:#374151;">Global ID</label>
            <form class="search-form" action="/master" method="GET">
                <input type="text" name="Global" class="search-input" placeholder="Enter Global ID" value="{unique_id}">
                <button type="submit" class="btn-search">Search</button>
                <a href="/master" class="btn-reset">Reset</a>
            </form>
        </div>
        {result_html}
    </div>"""
    

    extra_css = """
    .container { max-width:1400px; margin:0 auto; }
    
    .page-title { margin-left:-2%; text-align:center; background:#1e3a8a; padding:14px; border-radius:8px; margin-bottom:20px; font-size:32px; color:white;}
    
    .search-card {border:2px solid #1e3a8a; margin-left:20%; width:50%;
    background:white; padding:20px; border-radius:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom:25px; }
    
    .search-form { display:flex; gap:12px; margin-top:8px; }
    .search-input { flex:1; padding:12px 16px; border:1px solid #1e3a8a; border-radius:8px; font-size:15px; outline:none; }
    .search-input:focus { border-color:#0284c7; box-shadow:0 0 0 3px rgba(2,132,199,0.15); }
    .btn-search {background:#0284c7; color:white; border:none; padding:12px 28px; border-radius:8px; cursor:pointer; font-weight:bold; font-size:15px; }
    .btn-search:hover { background:linear-gradient(135deg, #10b981, #059669); }
    .btn-reset { background:#ef4444; color:white; text-decoration:none; padding:12px 28px; border-radius:8px; font-weight:bold; font-size:15px; display:flex; align-items:center; }
    .btn-reset:hover { background:#dc2626; }
    
    .result-card {background:lightblue; padding:30px; border-radius:40px; box-shadow:0 10px 15px -3px rgba(0,0,0,0.05); margin-top:-1%;}
    .result-card h3 { margin-top:0; border-bottom:2px solid #f3f4f6; padding-bottom:12px; margin-bottom:20px; color:#0f172a; }
    
    .detail-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    .detail-group { font-size:16px; color:black; line-height:1.5;font-weight:600;}
    .full-width { grid-column:span 3;}
    .label { font-weight:700; color:black; margin-right:4px; font-size:18px;}
    .desc-text { background:#f8fafc; padding:12px; border-radius:6px; border:1px solid #e2e8f0; margin-top:6px; white-space:pre-line; }
    .badge { padding:2px 8px; border-radius:4px; font-size:16px; font-weight:600; background:#e2e8f0; color:#334155; }
    
    .alert {margin-left:30%; width:30%; padding:16px; border-radius:8px; font-size:14px; text-align:center; font-weight:500; }
    .alert-error { background:#fee2e2; color:#b91c1c; border:1px solid #fecaca; }
    .alert-info  { background:#dbeafe; color:#1e40af; border:1px solid #bfdbfe; }
    
    .actions { margin-top:25px; padding-top:20px; border-top:1px solid #f3f4f6; display:flex; justify-content:flex-end; }
    
    .btn-edit { position: absolute;top:270px;right: 50px; background: #10b981; color: white; text-decoration: none; padding: 10px 22px; border-radius: 14px; font-weight: 600; font-size: 18px;}
    .btn-edit:hover { background:#059669; }
    
    """

    return page_shell("Master Tracker", "master", body, extra_css)


# ── Records / Reports ─────────────────────────────────────────────────────────

#old code
@app.route('/records')
@login_required
def records():
    data      = DDEntry.query.order_by(DDEntry.id).all()
    show_task = can_see_task()
    show_edit = can_edit()
    task_th   = "<th>Task</th>" if show_task else ""
    action_th = "<th>Action</th>" if show_edit else ""

    rows_html = ""
    for sno, row in enumerate(data, start=1):
        task_td = f"<td>{row.task or '-'}</td>" if show_task else ""

        if show_edit:
            action_td = f"""
            <td>
                <div style="display:flex;gap:8px;align-items:center;">
                    
                    <a href="/edit/{row.id}"
                       style="background:green;color:white;padding:6px 12px;border-radius:8px;text-decoration:none;font-size:12px;"> ✏️ Edit </a>
                    
                    
                    
<a href="/delete/{row.id}" onclick="return confirm('🗑️ Delete this record?')"
style="background:red;color:white;padding:6px 12px;border-radius:8px;text-decoration:none;font-size:12px;">🗑️ Delete</a>

                
                </div>
                
            </td>"""
        else:
            action_td = ""   # Viewers don't see buttons

        rows_html += f"""
        <tr>
            <td class="sno">{sno}</td>
            <td>{row.department or '-'}</td>
            <td>{row.work or '-'}</td>
            <td>{row.date or '-'}</td>
            <td>{row.Global or '-'}</td>
            <td>{row.purpose or '-'}</td>
            <td>{row.material or '-'}</td>
            <td>{row.other_material or '-'}</td>
            <td>{row.item_type or '-'}</td>
            <td>{row.other_type or '-'}</td>
            <td>{row.frequency or '-'}</td>
            <td>{row.quantity or '-'}</td>
            <td>{row.project or '-'}</td>
            <td>{row.description or '-'}</td>
            <td>{row.priority or '-'}</td>
            <td>{row.item or 'Pending'}</td>
            {task_td}
            {action_td}
        </tr>"""

    body = f"""
    <h1 style="text-align:center;background:#1e3a8a;padding:14px;border-radius:8px;margin-bottom:20px; color:white; margin-left:-1%;">
        D&D Department Records
    </h1>
    
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;flex-wrap:wrap;">
        
        
        <!--download data-->
        <a href="/download/excel"
           style="display:inline-flex;align-items:center;gap:6px;background:#4f6bed;color:white;
                  text-decoration:none;padding:10px 18px;border-radius:6px;font-weight:bold;font-size:14px; margin-left:-1%;">
            ⬇️ Download Excel
        </a>
        
        
        
        
    </div>
    <div class="table-container">
        <table>
        <thead>
            <tr>
                <th style="text-align:center;">S.No</th>
                <th>Department</th><th>Work Type</th><th>Date</th>
                <th>Global ID</th><th>Purpose</th><th>Material</th><th>Material (Other)</th>
                <th>Type</th><th>Type (Other)</th><th>Frequency</th><th>Quantity</th>
                <th>Project Name</th><th>Description</th><th>Priority</th>
                <th>Item Status</th>{task_th}{action_th}
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
        </table>
    </div>"""

    extra_css = """
    .table-container {overflow-x:auto; background:#fff; border-radius:10px; box-shadow:0 4px 10px rgba(0,0,0,.08);}
    
    .table-container {margin-left:-1%;overflow-x:auto; background:#fff; border-radius:10px; box-shadow:0 4px 10px rgba(0,0,0,.08);}
    
    table {min-width:1300px; border-collapse:collapse; }
    th { background:lightblue; color:#000; position:sticky; top:0; z-index:10; font-size:14px; padding:8px 6px; }
    
    th,td { padding:6px 6px; border-bottom:1px solid #e5e7eb; text-align:left; font-size:12px; }
    
    tr:hover { background:#f0f9ff; }
    .sno { font-weight:700; color:#1e3a8a; text-align:center; }
    """

    return page_shell("D&D Reports", "records", body, extra_css)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
    

