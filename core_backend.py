import streamlit as st
import hashlib
from datetime import datetime
from supabase import create_client

# ---------------- SUPABASE CONNECTION ----------------

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_PUBLIC_KEY = st.secrets["SUPABASE_PUBLIC_KEY"]
SUPABASE_SERVICE_KEY = st.secrets["SUPABASE_SERVICE_KEY"]

supabase_public = create_client(SUPABASE_URL, SUPABASE_PUBLIC_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ---------------- SECURITY ----------------

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

# ---------------- USERS ----------------

def create_user(username, password, role="staff"):
    hashed = hash_password(password)
    data = {
        "username": username,
        "password_hash": hashed,
        "role": role,
        "active": True,
        "failed_attempts": 0,
        "locked": False
    }
    return supabase_admin.table("users").insert(data).execute()

def get_user(username):
    res = supabase_public.table("users").select("*").eq("username", username).execute()
    if res.data:
        return res.data[0]
    return None

def ensure_default_admin():
    res = supabase_admin.table("users").select("*").execute()
    if not res.data:
        create_user("admin", "admin@123", "admin")

# ---------------- LOGIN (CRASH-PROOF) ----------------

def validate_login(username, password):
    user = get_user(username)
    if not user:
        return None

    # Locked?
    if user.get("locked", False):
        return None

    # Inactive?
    if not user.get("active", True):
        return None

    # Correct password
    if verify_password(password, user["password_hash"]):
        supabase_admin.table("users").update({
            "failed_attempts": 0,
            "last_login": datetime.utcnow().isoformat()
        }).eq("id", user["id"]).execute()

        return {
            "username": user["username"],
            "role": user["role"]
        }

    # Wrong password
    attempts = int(user.get("failed_attempts", 0)) + 1
    locked = attempts >= 3

    supabase_admin.table("users").update({
        "failed_attempts": attempts,
        "locked": locked
    }).eq("id", user["id"]).execute()

    return None

def record_logout(username):
    supabase_admin.table("users").update({
        "last_logout": datetime.utcnow().isoformat()
    }).eq("username", username).execute()

def unlock_user(user_id):
    return supabase_admin.table("users").update({
        "failed_attempts": 0,
        "locked": False
    }).eq("id", user_id).execute()

# ---------------- ACTIVITY LOG ----------------

def log_activity(username, action, category="general"):
    data = {
        "username": username,
        "action": action,
        "category": category
    }
    supabase_admin.table("activity_logs").insert(data).execute()

# ---------------- COUNTERS ----------------

def get_next_invoice_ref():
    now = datetime.now()
    month_key = now.strftime("%m/%y")

    res = supabase_admin.table("invoices").select("invoice_ref").like("invoice_ref", f"%/{month_key}/%").execute()

    nums = []
    if res.data:
        for row in res.data:
            try:
                nums.append(int(row["invoice_ref"].split("/")[-1]))
            except:
                pass

    next_num = max(nums) + 1 if nums else 1
    return f"BE/KNG/PMSG/QTN/{month_key}/{str(next_num).zfill(4)}"

def get_next_agreement_no():
    year = str(datetime.now().year)

    res = supabase_admin.table("agreements").select("agreement_no").like("agreement_no", f"%/{year}/%").execute()

    nums = []
    if res.data:
        for row in res.data:
            try:
                nums.append(int(row["agreement_no"].split("/")[-1]))
            except:
                pass

    next_num = max(nums) + 1 if nums else 1
    return f"AG/SG/APDCL/{year}/{str(next_num).zfill(4)}"

# ---------------- SAVE ----------------

def insert_invoice(data):
    return supabase_admin.table("invoices").insert(data).execute()

def insert_agreement(data):
    return supabase_admin.table("agreements").insert(data).execute()

# =====================================================
# ================= HISTORY ============================
# =====================================================

def fetch_invoices(role, username, search=None, limit=20, offset=0):
    query = supabase_admin.table("invoices").select("*", count="exact")

    if role != "admin":
        query = query.eq("created_by", username)

    if search:
        query = query.or_(
            f"customer_name.ilike.%{search}%,phone.ilike.%{search}%,invoice_ref.ilike.%{search}%"
        )

    query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
    res = query.execute()

    return {
        "data": res.data or [],
        "count": res.count or 0
    }

def fetch_agreements(role, username, search=None, limit=20, offset=0):
    query = supabase_admin.table("agreements").select("*", count="exact")

    if role != "admin":
        query = query.eq("created_by", username)

    if search:
        query = query.or_(
            f"customer_name.ilike.%{search}%,phone.ilike.%{search}%,agreement_no.ilike.%{search}%"
        )

    query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
    res = query.execute()

    return {
        "data": res.data or [],
        "count": res.count or 0
    }

def calculate_invoice_totals(invoices):
    total = 0
    for i in invoices:
        try:
            total += float(i.get("amount", 0))
        except:
            pass
    return {"count": len(invoices), "total_amount": total}

def calculate_agreement_totals(agreements):
    total = 0
    for a in agreements:
        try:
            total += float(a.get("amount", 0))
        except:
            pass
    return {"count": len(agreements), "total_amount": total}

# =====================================================
# ================= ANALYTICS ==========================
# =====================================================

def fetch_invoices_in_range(start_date, end_date):
    query = supabase_admin.table("invoices").select("*")
    if start_date:
        query = query.gte("created_at", start_date)
    if end_date:
        query = query.lte("created_at", end_date)
    return query.execute().data or []

def get_revenue_kpis(start_date, end_date):
    invoices = fetch_invoices_in_range(start_date, end_date)
    total_revenue = sum(float(i["amount"]) for i in invoices)
    total_count = len(invoices)
    avg_value = round(total_revenue / total_count, 2) if total_count else 0
    return {
        "total_revenue": total_revenue,
        "total_invoices": total_count,
        "avg_value": avg_value
    }

def get_daily_revenue_series(start_date, end_date):
    invoices = fetch_invoices_in_range(start_date, end_date)
    series = {}
    for inv in invoices:
        day = inv["created_at"][:10]
        series[day] = series.get(day, 0) + float(inv["amount"])
    return sorted(series.items())

def get_capacity_distribution(start_date, end_date):
    invoices = fetch_invoices_in_range(start_date, end_date)
    dist = {}
    for inv in invoices:
        cap = str(inv["capacity"])
        dist[cap] = dist.get(cap, 0) + 1
    return dist

def get_phase_split(start_date, end_date):
    invoices = fetch_invoices_in_range(start_date, end_date)
    split = {"Single Phase": 0, "Three Phase": 0}
    for inv in invoices:
        split[inv["phase"]] = split.get(inv["phase"], 0) + 1
    return split

def get_staff_performance(start_date, end_date):
    invoices = fetch_invoices_in_range(start_date, end_date)
    perf = {}
    for inv in invoices:
        user = inv["created_by"]
        perf[user] = perf.get(user, 0) + float(inv["amount"])
    return perf

def get_activity_timeline(start_date, end_date):
    query = supabase_admin.table("activity_logs").select("*")
    if start_date:
        query = query.gte("created_at", start_date)
    if end_date:
        query = query.lte("created_at", end_date)

    logs = query.execute().data or []
    timeline = {}
    for log in logs:
        day = log["created_at"][:10]
        timeline[day] = timeline.get(day, 0) + 1

    return sorted(timeline.items())
