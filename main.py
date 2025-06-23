import streamlit as st
import os
import shutil
import json
import datetime
from Utils.Storage import load_json, save_json
import pandas as pd
import io
from Utils.Export import patients_to_xml

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

# App title
st.title("🩺 Clinic Management System")

# --------------------------- Navigation ---------------------------
page = st.sidebar.radio("Navigation", ["Add Patient", "View Patients", "Earnings", "Admin Panel","Backup"])


# --------------------------- Add Patient Page ---------------------------
if page == "Add Patient":
    st.header("➕ Add Patient Record")

    with st.form("add_patient_form"):
        name = st.text_input("Patient Name")
        age = st.number_input("Age", min_value=0, max_value=120, step=1)
        phone = st.text_input("Phone Number", max_chars=10)
        phone_valid=phone.isdigit() and len(phone) == 10
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        if phone:  # Only show warning if something is entered
            if not phone.isdigit():
                st.warning("⚠️ Phone number must contain only digits.")
            elif len(phone) < 10:
                st.warning(f"⚠️ Phone number is too short ({len(phone)}/10 digits).")
            elif len(phone) > 10:
                st.warning(f"⚠️ Phone number is too long ({len(phone)}/10 digits).")
            elif not phone_valid:
                st.warning("⚠️ Phone number must be exactly 10 digits long.")
                
        symptoms = st.text_area("Symptoms")

        st.subheader("🧪 Select Tests and Enter Results/Cost")
        selected_tests = []
        total_test_cost = 0

        for test in tests:
            with st.expander(f"{test} (Base Price: ₹{tests[test]})", expanded=False):
                selected = st.checkbox(f"Include {test}", key=f"select_{test}")
                if selected:
                    value = st.text_input(f"Result for {test}", key=f"value_{test}")
                    price = st.number_input(f"Price for {test}", value=tests[test], key=f"price_{test}")
                    selected_tests.append({"name": test, "value": value, "cost": price})
                    total_test_cost += price

        consult_fee = st.number_input("Consultation Fee", value=200, min_value=0)
        total_amount = total_test_cost + consult_fee
        st.markdown(f"### 💰 Total Amount: ₹{total_amount}")

        submitted = st.form_submit_button("Save Patient Record")
        if submitted:
            st.session_state.confirm_add = True
            st.session_state.pending_patient = {
                "name": name,
                "age": age,
                "gender": gender,
                "phone": phone,
                "symptoms": symptoms,
                "tests": selected_tests,
                "consultation_fee": consult_fee,
                "total_amount": total_amount,
                "date": str(datetime.date.today())
            }

# Show second confirmation
if page == "Add Patient" and st.session_state.get("confirm_add", False):
    st.warning("⚠️ Are you sure you want to save this patient record?")
    col1, col2 = st.columns(2)
    if col1.button("✅ Confirm Save"):
        patient_record = st.session_state.pending_patient

        patients.append(patient_record)
        save_json(PATIENTS_FILE, patients)

        # Update earnings
        today = patient_record["date"]
        earnings[today] = earnings.get(today, 0) + patient_record["total_amount"]
        save_json(EARNINGS_FILE, earnings)

        st.success("✅ Patient record saved.")
        st.session_state.confirm_add = False
        del st.session_state.pending_patient
        st.rerun()

    if col2.button("❌ Cancel"):
        st.info("Cancelled adding patient.")
        st.session_state.confirm_add = False
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

    if not patients:
        st.info("No patient records yet.")
    else:
        search = st.text_input("🔍 Search by name or phone number")
        filtered = []
        for p in patients:
            if (search.lower() in p["name"].lower()) or (search in p["phone"]):
                filtered.append(p)

        if not search:
            filtered = patients

        st.write(f"Showing {len(filtered)} record(s)")
        for i, p in enumerate(reversed(filtered), 1):  # Newest first
            with st.expander(f"{i}. {p['name']} - ₹{p['total_amount']} on {p['date']}"):
                st.markdown(f"**Name:** {p['name']}")
                st.markdown(f"**Age:** {p['age']} years")   
                st.markdown(f"**Phone:** {p['phone']}")
                st.markdown(f"**Symptoms:** {p['symptoms']}")
                st.markdown(f"**Gender:** {p['gender']}")
                st.markdown(f"**Date:** {p['date']}")

                if p['tests']:
                    st.markdown("**Tests Done:**")
                    for test in p['tests']:
                        st.markdown(f"- {test['name']}: {test['value']} (₹{test['cost']})")
                else:
                    st.markdown("No tests performed.")

                st.markdown(f"**Consultation Fee:** ₹{p['consultation_fee']}")
                st.markdown(f"**Total Paid:** ₹{p['total_amount']}")

                # Add delete button
                if st.button("🗑️ Delete Record", key=f"delete_{i}"):
                    patients.remove(p)

                    # Adjust earnings
                    earnings[p["date"]] -= p["total_amount"]
                    if earnings[p["date"]] <= 0:
                        earnings.pop(p["date"])  # Remove date if no money left

                    save_json(PATIENTS_FILE, patients)
                    save_json(EARNINGS_FILE, earnings)
                    st.success("Record deleted.")
                    st.rerun()

# --------------------------- Earnings Summary Page ---------------------------
elif page == "Earnings":
    st.header("💰 Clinic Earnings Summary")

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
                        st.markdown(f"**🎂 DOB:** {patient['dob']}  (Age {patient['age']})")
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