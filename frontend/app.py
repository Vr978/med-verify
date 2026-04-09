import streamlit as st
import requests, os
from dotenv import load_dotenv
load_dotenv()

API = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Auth Demo", page_icon="🔐", layout="centered")

if "access" not in st.session_state: st.session_state.access = None
if "refresh" not in st.session_state: st.session_state.refresh = None
if "email" not in st.session_state: st.session_state.email = None

st.title("🔐 Auth (FastAPI + PostgreSQL + bcrypt)")

tab1, tab2, tab3 = st.tabs(["Register", "Login", "Profile"])

with tab1:
    st.subheader("Create an account")
    email = st.text_input("Email", key="reg_email")
    pw = st.text_input("Password", type="password", key="reg_pw")
    if st.button("Register"):
        try:
            r = requests.post(f"{API}/auth/register", json={"email": email, "password": pw}, timeout=10)
            if r.status_code in (200,201):
                data = r.json()
                st.session_state.access = data["access_token"]
                st.session_state.refresh = data["refresh_token"]
                st.session_state.email = email
                st.success("Registered & signed in!")
            else:
                st.error(f"Register failed: {r.text}")
        except Exception as e:
            st.error(str(e))

with tab2:
    st.subheader("Sign in")
    email = st.text_input("Email", key="login_email")
    pw = st.text_input("Password", type="password", key="login_pw")
    if st.button("Login"):
        try:
            r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                st.session_state.access = data["access_token"]
                st.session_state.refresh = data["refresh_token"]
                st.session_state.email = email
                st.success("Logged in!")
            else:
                st.error(f"Login failed: {r.text}")
        except Exception as e:
            st.error(str(e))

with tab3:
    st.subheader("Your profile")
    if st.session_state.access:
        h = {"Authorization": f"Bearer {st.session_state.access}"}
        r = requests.get(f"{API}/users/me", headers=h)
        if r.status_code == 200:
            st.json(r.json())
        else:
            st.warning("Access token invalid/expired. Try refresh.")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Refresh Token"):
                rr = requests.post(f"{API}/auth/refresh", json={"refresh_token": st.session_state.refresh})
                if rr.status_code == 200:
                    data = rr.json()
                    st.session_state.access = data["access_token"]
                    st.session_state.refresh = data["refresh_token"]
                    st.success("Token refreshed.")
                else:
                    st.error(f"Refresh failed: {rr.text}")
        with col2:
            if st.button("Logout"):
                requests.post(f"{API}/auth/logout", json={"refresh_token": st.session_state.refresh})
                st.session_state.access = None
                st.session_state.refresh = None
                st.session_state.email = None
                st.success("Logged out.")
        with col3:
            st.write("")
    else:
        st.info("Not signed in.")
