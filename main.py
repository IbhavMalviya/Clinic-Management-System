import streamlit as st
import os
import shutil
import json
import datetime
from Utils.Storage import load_json, save_json
import pandas as pd
import io
from Utils.Export import patients_to_xml
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "backup")
os.makedirs(BACKUP_DIR, exist_ok=True)

# --------------------------- Setup ---------------------------
st.set_page_config(page_title="Clinic Management App", layout="wide")

# File paths
DATA_DIR = "data"
PATIENTS_FILE = os.path.join(DATA_DIR, "patients.json")
EARNINGS_FILE = os.path.join(DATA_DIR, "earnings.json")
TESTS_FILE = os.path.join(DATA_DIR, "tests.json")

# Load data or create default
patients = load_json(PATIENTS_FILE, [])
earnings = load_json(EARNINGS_FILE, {})
tests = load_json(TESTS_FILE, {})

st.markdown("""
    <h1 style='font-family: "Trebuchet MS", sans-serif; color: #008000;'>
        🩺 Dr. Pramod Malviya
    </h1>
""", unsafe_allow_html=True)
# --------------------------- Navigation ---------------------------
page = st.sidebar.radio("Navigation", ["Add Patient", "View Patients", "Earnings", "Admin Panel", "Backup"])

# --------------------------- Add Patient Page ---------------------------
if page == "Add Patient":
    st.header("➕ Add Patient Record")
    with st.form("add_patient_form"):
        st.subheader("👤 Patient Information")
        col1, col2 = st.columns(2)
        with col1:
            patient_name = st.text_input("Patient Name")
            age = st.number_input("Age", min_value=0, max_value=120, step=1)
        with col2:
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            phone = st.text_input("Phone Number", max_chars=10)

        phone_valid = phone.isdigit() and len(phone) == 10
        if phone:
            if not phone.isdigit():
                st.warning("⚠️ Phone number must contain only digits.")
            elif len(phone) < 10:
                st.warning(f"⚠️ Phone number is too short ({len(phone)}/10 digits).")
            elif len(phone) > 10:
                st.warning(f"⚠️ Phone number is too long ({len(phone)}/10 digits).")

        if patient_name and len(patient_name.strip()) == 0:
            st.warning("⚠️ Name cannot be empty.")

        symptoms = st.text_area("📝 Symptoms")

        # Initialize selected_tests once
        if "selected_tests" not in st.session_state:
            st.session_state.selected_tests = []

        # Select multiple tests with cost info
        test_options = [f"{test_name} (₹{price})" for test_name, price in tests.items()]
        test_lookup = {f"{test_name} (₹{price})": test_name for test_name, price in tests.items()}
        selected_option_labels = st.multiselect("🧪 Search and Select Tests", options=test_options)

        # Update selected_tests reactively
        selected_names = [test_lookup[label] for label in selected_option_labels]
        st.session_state.selected_tests = [
            test for test in st.session_state.selected_tests if test["name"] in selected_names
        ]
        # Add newly selected tests if not present
        existing_names = {test["name"] for test in st.session_state.selected_tests}
        for test_name in selected_names:
            if test_name not in existing_names:
                st.session_state.selected_tests.append({
                    "name": test_name,
                    "value": "",
                    "cost": tests[test_name]
                })

        # Calculate test costs live
        total_test_cost = 0
        if st.session_state.selected_tests:
            st.markdown("### ✅ Selected Tests")
            for i, test in enumerate(st.session_state.selected_tests):
                col1, col2, col3 = st.columns([4, 3, 2])
                col1.markdown(f"**{test['name']}**")
                test['value'] = col2.text_input("Result", value=test.get('value', ''), key=f"res_{i}")
                test['cost'] = col3.number_input("₹", value=test.get('cost', 0), min_value=0, key=f"cost_{i}")
                total_test_cost += test["cost"]

        # Live consultation fee input (will also trigger re-render)
        consult_fee = st.number_input("💵 Consultation Fee", value=st.session_state.get("consult_fee", 350), min_value=0, key="consult_fee")

        # Calculate and show total
        total_amount = total_test_cost + consult_fee
        st.markdown(f"### 💰 Total Amount: ₹{total_amount}")
        submitted_col1, submitted_col2 = st.columns([1, 1])
        calculate_pressed = submitted_col1.form_submit_button("🧮 Calculate Total")
        save_pressed = submitted_col2.form_submit_button("💾 Save Patient Record")
        # Compute total test cost
        total_test_cost = sum(test["cost"] for test in st.session_state.selected_tests)
        total_amount = total_test_cost + st.session_state.consult_fee
        # Show calculated total if Calculate button is clicked
        
        if save_pressed:
            if not patient_name.strip():
                st.error("❌ Patient name is required. Record not saved.")
            else:
                st.session_state.confirm_add = True
                now = datetime.datetime.now()
                st.session_state.pending_patient = {
                "name": patient_name,
                "age": age,
                "gender": gender,
                "phone": phone,
                "symptoms": symptoms,
                "tests": st.session_state.selected_tests,
                "consultation_fee": consult_fee,
                "total_amount": total_amount,
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M")
            }


# Show second confirmation
if page == "Add Patient" and st.session_state.get("confirm_add", False):
    st.warning("⚠️ Are you sure you want to save this patient record?")
    col1, col2 = st.columns(2)

    if col1.button("✅ Confirm Save"):
        pending = st.session_state.get("pending_patient")

        if not pending or not pending.get("name", "").strip():
            st.error("❌ Patient name is required. Record not saved.")
        else:
            patients.append(pending)
            save_json(PATIENTS_FILE, patients)

            today = pending["date"]
            earnings[today] = earnings.get(today, 0) + pending["total_amount"]
            save_json(EARNINGS_FILE, earnings)

            st.success("✅ Patient record saved.")
            st.session_state.confirm_add = False
            del st.session_state.pending_patient
            st.rerun()

    if col2.button("❌ Cancel"):
        st.info("Cancelled adding patient.")
        st.session_state.confirm_add = False
        if "pending_patient" in st.session_state:
            del st.session_state.pending_patient
        st.rerun()


# --------------------------- Admin Panel ---------------------------
elif page == "Admin Panel":
    st.header("🔐 Admin Panel")

    config_path = os.path.join(DATA_DIR, "admin_config.json")
    config = load_json(config_path, {"admin_password": "1234"})

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        input_pass = st.text_input("Enter admin password", type="password")
        if st.button("Login"):
            if input_pass == config["admin_password"]:
                st.session_state.authenticated = True
                st.success("Access granted.")
                st.rerun()
            else:
                st.error("Incorrect password.")
    else:
        st.success("🔓 Admin Access Granted")

        st.subheader("🧪 Existing Tests")
        to_delete = None
        updated = False

        for test, price in tests.items():
            col1, col2, col3 = st.columns([4, 2, 1])
            new_name = col1.text_input("Test Name", value=test, key=f"name_{test}")
            new_price = col2.number_input("Price", value=price, key=f"cost_{test}")
            if col3.button("🗑️", key=f"del_{test}"):
                to_delete = test
            elif new_name != test or new_price != price:
                tests.pop(test)
                tests[new_name] = new_price
                updated = True
                break

        if to_delete:
            tests.pop(to_delete)
            save_json(TESTS_FILE, tests)
            st.rerun()

        if updated:
            save_json(TESTS_FILE, tests)
            st.success("✅ Test updated.")
            st.rerun()

        st.divider()
        st.subheader("➕ Add New Test")
        new_test = st.text_input("New Test Name", key="new_test")
        new_price = st.number_input("New Test Price", min_value=0, step=10, key="new_price")
        if st.button("Add Test"):
            if new_test.strip() == "":
                st.warning("Test name cannot be empty.")
            elif new_test in tests:
                st.warning("Test already exists.")
            else:
                tests[new_test] = new_price
                save_json(TESTS_FILE, tests)
                st.success(f"✅ Test '{new_test}' added.")
                st.rerun()
        st.divider()
# --------------------------- View Patients Page ---------------------------
elif page == "View Patients":
    st.header("📋 Patient Records")
        # Date range filter
    st.subheader("📅 Filter by Date Range")
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date", value=datetime.date.today() - datetime.timedelta(days=7))
    end_date = col2.date_input("End Date", value=datetime.date.today())

    if start_date > end_date:
        st.warning("⚠️ Start date must be before or equal to end date.")

    if not patients:
        st.info("No patient records yet.")
    else:
        search = st.text_input("🔍 Search by name or phone number")
        filtered = []
        for p in patients:
            try:
                patient_date = datetime.datetime.strptime(p['date'], "%Y-%m-%d").date()
            except:
                continue  # skip invalid entries

            if start_date <= patient_date <= end_date:
                 if not search or (search.lower() in p["name"].lower()) or (search in p["phone"]):
                    filtered.append(p)



        st.write(f"Showing {len(filtered)} record(s)")
        for i, p in enumerate(reversed(filtered), 1):  # Newest first
            try:
                dt = datetime.datetime.strptime(f"{p['date']} {p.get('time', '00:00')}", "%Y-%m-%d %H:%M")
                formatted_date = dt.strftime("%d-%m-%Y")
                formatted_time = dt.strftime("%I:%M %p")
            except:
                formatted_date = p['date']
                formatted_time = p.get('time', 'Not recorded')

            with st.expander(f"{i}. {p['name']} - ₹{p['total_amount']} on {formatted_date} at {formatted_time}"):
                if st.session_state.get(f"editing_{i}", False):
                    new_name = st.text_input("Name", value=p['name'], key=f"edit_name_{i}")
                    new_age = st.number_input("Age", value=p['age'], min_value=0, max_value=120, key=f"edit_age_{i}")
                    new_phone = st.text_input("Phone", value=p['phone'], key=f"edit_phone_{i}")
                    new_symptoms = st.text_area("Symptoms", value=p['symptoms'], key=f"edit_symptoms_{i}")
                    new_gender = st.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(p.get("gender", "Other")), key=f"edit_gender_{i}")
                    
                    new_tests = []
                    test_total = 0
                    for j, test in enumerate(p.get("tests", [])):
                        col1, col2, col3 = st.columns([4, 3, 2])
                        test_name = col1.text_input("Test Name", value=test['name'], key=f"edit_test_name_{i}_{j}")
                        test_value = col2.text_input("Result", value=test['value'], key=f"edit_test_val_{i}_{j}")
                        test_cost = col3.number_input("₹", value=test['cost'], min_value=0, key=f"edit_test_cost_{i}_{j}")
                        new_tests.append({"name": test_name, "value": test_value, "cost": test_cost})
                        test_total += test_cost

                    new_fee = st.number_input("Consultation Fee", value=p["consultation_fee"], min_value=0, key=f"edit_fee_{i}")
                    new_total = test_total + new_fee
                    st.markdown(f"### 💰 Updated Total: ₹{new_total}")

                    col_save, col_cancel = st.columns(2)
                    if col_save.button("💾 Save Changes", key=f"save_{i}"):
                        p.update({
                            "name": new_name,
                            "age": new_age,
                            "phone": new_phone,
                            "symptoms": new_symptoms,
                            "gender": new_gender,
                            "tests": new_tests,
                            "consultation_fee": new_fee,
                            "total_amount": new_total
                        })

                        earnings[p["date"]] = sum(pat["total_amount"] for pat in patients if pat["date"] == p["date"])
                        save_json(PATIENTS_FILE, patients)
                        save_json(EARNINGS_FILE, earnings)

                        st.success("✅ Patient record updated.")
                        st.session_state[f"editing_{i}"] = False
                        st.rerun()

                    if col_cancel.button("❌ Cancel", key=f"cancel_{i}"):
                        st.session_state[f"editing_{i}"] = False
                        st.rerun()

                else:
                    st.markdown(f"**Name:** {p['name']}")
                    st.markdown(f"**Age:** {p['age']} years")
                    st.markdown(f"**Phone:** {p['phone']}")
                    st.markdown(f"**Symptoms:** {p['symptoms']}")
                    st.markdown(f"**Gender:** {p.get('gender', 'Not specified')}")
                    st.markdown(f"**Date:** {formatted_date}")
                    st.markdown(f"**Time:** {formatted_time}")

                    if p['tests']:
                        st.markdown("**Tests Done:**")
                        for test in p['tests']:
                            st.markdown(f"- {test['name']}: {test['value']} (₹{test['cost']})")
                    else:
                        st.markdown("No tests performed.")

                    st.markdown(f"**Consultation Fee:** ₹{p['consultation_fee']}")
                    st.markdown(f"**Total Paid:** ₹{p['total_amount']}")

                    col_edit, col_delete = st.columns(2)
                    if col_edit.button("✏️ Edit Record", key=f"edit_{i}"):
                        st.session_state[f"editing_{i}"] = True
                        st.rerun()

                    if col_delete.button("🗑️ Delete Record", key=f"delete_{i}"):
                        patients.remove(p)
                        if p["date"] in earnings:
                            earnings[p["date"]] -= p["total_amount"]
                            if earnings[p["date"]] <= 0:
                                earnings.pop(p["date"])
                        save_json(PATIENTS_FILE, patients)
                        save_json(EARNINGS_FILE, earnings)
                        st.success("Record deleted.")
                        st.rerun()



# --------------------------- Earnings Summary Page ---------------------------
elif page == "Earnings":
    st.header("💰 Clinic Earnings Summary")

    # Load admin config
    config_path = os.path.join(DATA_DIR, "admin_config.json")
    config = load_json(config_path, {"admin_password": "1234"})

    # Check authentication
    if "earnings_authenticated" not in st.session_state:
        st.session_state.earnings_authenticated = False

    if not st.session_state.earnings_authenticated:
        earnings_pass = st.text_input("Enter password to view earnings", type="password")
        if st.button("Unlock Earnings"):
            if earnings_pass == config.get("admin_password", "1234"):
                st.session_state.earnings_authenticated = True
                st.success("✅ Access granted.")
                st.rerun()
            else:
                st.error("❌ Incorrect password.")
    else:
        # ---------- Earnings content (no changes below this line) ----------
        if not earnings:
            st.info("No earnings data available yet.")
        else:
            today = datetime.date.today()
            today_str = str(today)
            past_7 = [(today - datetime.timedelta(days=i)).isoformat() for i in range(7)]
            this_month = today.strftime("%Y-%m")

            total_today = earnings.get(today_str, 0)
            total_week = sum(earnings.get(date, 0) for date in past_7)
            total_month = sum(amount for date, amount in earnings.items() if date.startswith(this_month))

            st.metric("🗓️ Today's Earnings", f"₹{total_today}")
            st.metric("📅 Last 7 Days", f"₹{total_week}")
            st.metric("📆 This Month", f"₹{total_month}")

            st.divider()
            st.subheader("📊 Click a Date to View Patients")

            # Group patients by date
            grouped = {}
            for p in patients:
                grouped.setdefault(p["date"], []).append(p)

            for date in sorted(grouped.keys(), reverse=True):
                with st.expander(f"📅 {date} — ₹{earnings.get(date, 0)}"):
                    for idx, patient in enumerate(grouped[date], 1):
                        with st.expander(f"{idx}. {patient['name']} — ₹{patient['total_amount']}"):
                            st.markdown(f"**🧍 Name:** {patient['name']}")
                            st.markdown(f"**📞 Phone:** {patient['phone']}")
                            st.markdown(f"**👤 Age:** {patient['age']} years")
                            st.markdown(f"**🤒 Symptoms:** {patient['symptoms']}")

                            if patient['tests']:
                                st.markdown("**🧪 Tests:**")
                                for test in patient['tests']:
                                    st.markdown(f"- {test['name']}: {test['value']} (₹{test['cost']})")
                            else:
                                st.markdown("No tests recorded.")

                            st.markdown(f"**💵 Consultation Fee:** ₹{patient['consultation_fee']}")
                            st.markdown(f"**💰 Total Paid:** ₹{patient['total_amount']}")
                            st.markdown(f"**📅 Date:** {patient['date']}")

# --------------------------- Backup Page ---------------------------
elif page == "Backup":
    st.header("📦 Manual XML Backup")

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    backup_filename = f"patients_backup_{today_str}.xml"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    if st.button("🧾 Backup Patient Records Now"):
        try:
            pretty_xml = patients_to_xml(patients)
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(pretty_xml)
            st.success(f"✅ Backup saved as `{backup_filename}`")
        except Exception as e:
            st.error(f"❌ Backup failed: {e}")

    st.markdown("### 📁 Existing XML Backups:")

    backup_files = sorted(os.listdir(BACKUP_DIR), reverse=True)
    for file in backup_files:
        if file.endswith(".xml"):
            file_path = os.path.join(BACKUP_DIR, file)
            with open(file_path, "rb") as f:
                st.download_button(
                    label=f"⬇️ Download {file}",
                    data=f.read(),
                    file_name=file,
                    mime="application/xml"
                )
