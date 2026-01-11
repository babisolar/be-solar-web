import streamlit as st
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import plotly.graph_objects as go

from core_backend import (
    validate_login,
    ensure_default_admin,
    log_activity,
    record_logout,
    unlock_user,
    list_users,
    get_next_invoice_ref,
    get_next_agreement_no,
    insert_invoice,
    insert_agreement,
    fetch_invoices,
    fetch_agreements,
    calculate_invoice_totals,
    calculate_agreement_totals,
    get_revenue_kpis,
    get_daily_revenue_series,
    get_capacity_distribution,
    get_phase_split,
    get_staff_performance,
    get_activity_timeline,
)

st.set_page_config(page_title="BE Solar Control Center", layout="wide")

# ---------------- THEME ----------------

def inject_dark_cyber_css():
    st.markdown("""
    <style>
    body { background-color: #020617; color: white; }
    [data-testid="stSidebar"] { background-color: #020617; }
    h1, h2, h3 { color: #7dd3fc; }
    .glass {
        background: rgba(15,23,42,0.6);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 0 25px rgba(56,189,248,0.15);
        border: 1px solid rgba(56,189,248,0.2);
    }
    .kpi {
        font-size: 28px;
        font-weight: bold;
        color: #e0f2fe;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------- INIT ----------------

ensure_default_admin()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None

# ---------------- LOGIN ----------------

def login_page():
    inject_dark_cyber_css()
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            user = validate_login(username, password)
        except Exception as e:
            st.error("Login system error.")
            return

        if user:
            st.session_state.logged_in = True
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            log_activity(user["username"], "Logged in", "auth")
            st.rerun()
        else:
            st.error("Invalid credentials or account locked.")

def logout():
    try:
        record_logout(st.session_state.username)
        log_activity(st.session_state.username, "Logged out", "auth")
    except:
        pass

    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.rerun()

# ---------------- SIDEBAR ----------------

def sidebar():
    with st.sidebar:
        st.markdown("## ⚡ BE Solar")

        if st.session_state.username:
            st.markdown(f"**User:** {st.session_state.username}")
            st.markdown(f"**Role:** {st.session_state.role}")
        else:
            st.markdown("Not logged in")

        st.markdown("---")

        if st.session_state.role == "admin":
            page = st.radio("Navigation", [
                "Dashboard",
                "Generate Documents",
                "Invoice History",
                "Agreement History",
                "Staff Security"
            ])
        else:
            page = st.radio("Navigation", [
                "Generate Documents",
                "Invoice History",
                "Agreement History"
            ])

        st.markdown("---")
        if st.button("Logout"):
            logout()

    return page
# ---------------- GENERATE DOCUMENTS PAGE ----------------

RATE_PER_KW = 70000

def generate_documents_page():
    inject_dark_cyber_css()
    st.title("📄 Generate Invoice & Agreement")

    with st.container():
        st.markdown('<div class="glass">', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            customer_name = st.text_input("Customer Name")
            phone = st.text_input("Phone Number")
            address = st.text_area("Address")
            consumer_no = st.text_input("APDCL Consumer Number")

        with col2:
            subdivision = st.text_input("Subdivision")
            capacity = st.selectbox("System Capacity (kW)", [3, 4.5, 5, 10])
            phase = "Three Phase" if capacity >= 5 else "Single Phase"
            total_amount = int(capacity * RATE_PER_KW)

            st.info(f"Phase: {phase}")
            st.success(f"Total: ₹ {total_amount:,}")

        st.markdown("### Witnesses")
        w1_name = st.text_input("Witness 1 Name")
        w1_phone = st.text_input("Witness 1 Phone")
        w2_name = st.text_input("Witness 2 Name")
        w2_phone = st.text_input("Witness 2 Phone")

        if st.button("🚀 Generate Documents"):
            if not customer_name or not phone:
                st.error("Customer name and phone are required.")
                return

            invoice_ref = get_next_invoice_ref()
            agreement_no = get_next_agreement_no()

            now = datetime.now()

            insert_invoice({
                "invoice_ref": invoice_ref,
                "customer_name": customer_name,
                "phone": phone,
                "address": address,
                "consumer_no": consumer_no,
                "subdivision": subdivision,
                "capacity": capacity,
                "phase": phase,
                "amount": total_amount,
                "created_by": st.session_state.username,
                "created_at": now.isoformat()
            })

            insert_agreement({
                "agreement_no": agreement_no,
                "customer_name": customer_name,
                "phone": phone,
                "address": address,
                "consumer_no": consumer_no,
                "subdivision": subdivision,
                "capacity": capacity,
                "phase": phase,
                "amount": total_amount,
                "created_by": st.session_state.username,
                "created_at": now.isoformat()
            })

            log_activity(
                st.session_state.username,
                f"Generated {invoice_ref} & {agreement_no}",
                "generate"
            )

            st.success("Documents saved successfully!")

            st.markdown(f"""
            **Invoice Ref:** `{invoice_ref}`  
            **Agreement No:** `{agreement_no}`
            """)

        st.markdown('</div>', unsafe_allow_html=True)
ROWS_PER_PAGE = 20

# ---------------- INVOICE HISTORY ----------------

def invoice_history_page():
    inject_dark_cyber_css()
    st.title("📑 Invoice History")

    with st.container():
        st.markdown('<div class="glass">', unsafe_allow_html=True)

        col1, col2 = st.columns([3,1])
        with col1:
            search = st.text_input("Search (Name / Phone / Invoice No)")
        with col2:
            page_no = st.number_input("Page", min_value=1, value=1)

        offset = (page_no - 1) * ROWS_PER_PAGE

        result = fetch_invoices(
            role=st.session_state.role,
            username=st.session_state.username,
            search=search,
            limit=ROWS_PER_PAGE,
            offset=offset
        )

        invoices = result["data"]

        if invoices:
            st.dataframe(invoices, use_container_width=True)

            totals = calculate_invoice_totals(invoices)
            st.markdown(
                f"**Records:** {totals['count']} | **Total Amount:** ₹ {totals['total_amount']:,}"
            )
        else:
            st.info("No invoices found.")

        st.markdown('</div>', unsafe_allow_html=True)

# ---------------- AGREEMENT HISTORY ----------------

def agreement_history_page():
    inject_dark_cyber_css()
    st.title("📑 Agreement History")

    with st.container():
        st.markdown('<div class="glass">', unsafe_allow_html=True)

        col1, col2 = st.columns([3,1])
        with col1:
            search = st.text_input("Search (Name / Phone / Agreement No)")
        with col2:
            page_no = st.number_input("Page", min_value=1, value=1)

        offset = (page_no - 1) * ROWS_PER_PAGE

        result = fetch_agreements(
            role=st.session_state.role,
            username=st.session_state.username,
            search=search,
            limit=ROWS_PER_PAGE,
            offset=offset
        )

        agreements = result["data"]

        if agreements:
            st.dataframe(agreements, use_container_width=True)

            totals = calculate_agreement_totals(agreements)
            st.markdown(
                f"**Records:** {totals['count']} | **Total Amount:** ₹ {totals['total_amount']:,}"
            )
        else:
            st.info("No agreements found.")

        st.markdown('</div>', unsafe_allow_html=True)
# ---------------- DASHBOARD ----------------

def dashboard_page():
    if st.session_state.role != "admin":
        st.error("Access denied.")
        return

    inject_dark_cyber_css()
    st.title("⚡ Command Center")

    st_autorefresh(interval=30 * 1000, key="dashboard_refresh")

    # Date range
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date")
    with col2:
        end_date = st.date_input("End Date")

    start = str(start_date) if start_date else None
    end = str(end_date) if end_date else None

    kpis = get_revenue_kpis(start, end)
    daily_series = get_daily_revenue_series(start, end)
    capacity_dist = get_capacity_distribution(start, end)
    phase_split = get_phase_split(start, end)
    staff_perf = get_staff_performance(start, end)
    activity_series = get_activity_timeline(start, end)

    # KPI Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="glass"><div class="kpi">₹ {kpis["total_revenue"]:,}</div>Total Revenue</div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="glass"><div class="kpi">{kpis["total_invoices"]}</div>Total Invoices</div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="glass"><div class="kpi">₹ {kpis["avg_value"]:,}</div>Avg Deal</div>', unsafe_allow_html=True)
    with c4:
        top_capacity = max(capacity_dist, key=capacity_dist.get) if capacity_dist else "--"
        st.markdown(f'<div class="glass"><div class="kpi">{top_capacity}</div>Top Capacity</div>', unsafe_allow_html=True)

    # Charts
    col5, col6 = st.columns(2)

    with col5:
        if daily_series:
            dates, values = zip(*daily_series)
            fig1 = px.line(x=dates, y=values, title="Revenue Timeline")
            fig1.update_layout(template="plotly_dark")
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("No revenue data.")

    with col6:
        if capacity_dist:
            fig2 = px.bar(x=list(capacity_dist.keys()), y=list(capacity_dist.values()), title="Capacity Distribution")
            fig2.update_layout(template="plotly_dark")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No capacity data.")

    col7, col8 = st.columns(2)

    with col7:
        if phase_split:
            fig3 = px.pie(values=list(phase_split.values()), names=list(phase_split.keys()), title="Phase Split")
            fig3.update_layout(template="plotly_dark")
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No phase data.")

    with col8:
        if staff_perf:
            fig4 = px.bar(x=list(staff_perf.keys()), y=list(staff_perf.values()), title="Staff Performance")
            fig4.update_layout(template="plotly_dark")
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No staff data.")

    if activity_series:
        ad, av = zip(*activity_series)
        fig5 = px.line(x=ad, y=av, title="Activity Timeline")
        fig5.update_layout(template="plotly_dark")
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.info("No activity data.")
# ---------------- STAFF SECURITY ----------------

def staff_security_page():
    inject_dark_cyber_css()
    st.title("🔐 Staff Security Control")

    if st.session_state.role != "admin":
        st.error("Access denied.")
        return

    users = list_users()

    if not users:
        st.info("No users found.")
        return

    for u in users:
        with st.container():
            st.markdown('<div class="glass">', unsafe_allow_html=True)

            col1, col2, col3, col4, col5, col6 = st.columns([2,1,1,1,2,2])

            with col1:
                st.write(f"👤 {u['username']}")
            with col2:
                st.write(u["role"])
            with col3:
                st.write("🔴 Locked" if u.get("locked") else "🟢 Active")
            with col4:
                st.write(f"Fails: {u.get('failed_attempts', 0)}")
            with col5:
                st.write(f"Last login: {u.get('last_login', '—')}")
            with col6:
                if u.get("locked"):
                    if st.button("Unlock", key=f"unlock_{u['id']}"):
                        unlock_user(u["id"])
                        log_activity(
                            st.session_state.username,
                            f"Unlocked {u['username']}",
                            "security"
                        )
                        st.success(f"{u['username']} unlocked.")
                        st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)
            st.divider()

# ---------------- ROUTER ----------------

def main_app():
    page = sidebar()

    if page == "Dashboard":
        dashboard_page()
    elif page == "Generate Documents":
        generate_documents_page()
    elif page == "Invoice History":
        invoice_history_page()
    elif page == "Agreement History":
        agreement_history_page()
    elif page == "Staff Security":
        staff_security_page()

# ---------------- ENTRY ----------------

if not st.session_state.logged_in:
    login_page()
else:
    main_app()

