import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
import bcrypt

st.set_page_config(layout='wide')

def load_data(defined_sheet):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Directly access Streamlit secrets and parse them as JSON
    credentials_dict = st.secrets["thunder"] 
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("dailytaskDB").worksheet(defined_sheet)
    
    return sheet

def load_users_sheet(defined_sheet):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Directly access Streamlit secrets and parse them as JSON
    credentials_dict = st.secrets["thunder"] 
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("dailytaskDB").worksheet(defined_sheet)
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return df


# Session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

# Load Users
users_df = load_users_sheet("Users")

def login(email, password):
    user = users_df[users_df['Email'] == email]
    if user.empty:
        return False, None
    stored_hash = user.iloc[0]['Password'].encode('utf-8')
    if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
        return True, user.iloc[0]
    return False, None

def logout():
    st.session_state.authenticated = False
    st.session_state.user_role = None

# Login form inside st.form
if not st.session_state.authenticated:
    login_column_1,login_column_2,login_column_3 = st.columns(3)
    with login_column_2:
        st.title("Admin Login")
        
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

            if submitted:
                success, user_data = login(email, password)
                if success:
                    if user_data['Role'].lower() == 'admin':
                        st.session_state.authenticated = True
                        st.session_state.user_role = user_data['Role']
                        st.toast("Login successful!")
                        st.rerun()
                    else:
                        st.error("Access denied: Admins only.")
                else:
                    st.error("Invalid credentials")
        
        st.stop()


# Main dashboard
column_header_1,column_header_2 = st.columns([0.9,0.1])
with column_header_1:
    st.title("Admin Analytics Dashboard")
with column_header_2:
    # Logout option
    if st.button("Logout"):
        logout()
        st.cache_data.clear()
        st.rerun()

tab_1,tab_2,tab_3 = st.tabs(['User Summary','User Details','Task Details'])
with tab_1:
    st.subheader("User Summary")
    # Example analytics
    cols1,cols2,cols3,cols4 = st.columns(4)

    with cols1:
        st.metric(label='Total users in DB', value= len(users_df),border=True)
    with cols2:
        st.metric(label='Total users in DB (Users)', value= len(users_df[users_df['Role'] == 'user']),border=True)
    with cols3:
        st.metric(label='Total users in DB (Admin)', value= len(users_df[users_df['Role'] == 'admin']),border=True)

    st.subheader("Department Breakdown")
    st.bar_chart(users_df['Department'].value_counts())

    st.subheader("Shift Start Time Distribution")
    shift_start_counts = users_df['Start Time'].value_counts().sort_index()
    st.line_chart(shift_start_counts)


with tab_2:
    tab1,tab2,tab3 = st.tabs(['create user','Modify User','Delete Users'])
    with tab1:
        tab1_col1, tab1_col2, tab1_col3 = st.columns(3)
        with tab1_col2:
            st.subheader("Create New User")

            with st.form("create_user_form"):
                new_email = st.text_input("New User Email")
                new_role = st.selectbox("Role", options=["user", "admin"])
                submit_user = st.form_submit_button("Create User")

                if submit_user:
                    if not new_email:
                        st.warning("Please enter an email address.")
                    elif new_email in users_df['Email'].values:
                        st.error("User with this email already exists.")
                    else:
                        try:
                            # Add the new user to the sheet with empty password
                            new_user = [new_email, "", new_role]
                            sheet = load_data('Users')
                            sheet.append_row(new_user)
                            st.success(f"User {new_email} created successfully!")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Failed to create user: {e}")

    with tab2:
        tab2_col1, tab2_col2, tab2_col3 = st.columns(3)
        with tab2_col2:
            st.subheader("Reset User Password")

            with st.form("reset_password_form"):
                email_to_reset = st.selectbox("Select user to reset password", users_df["Email"].values, key="reset_user")
                reset_button = st.form_submit_button("Reset Password")

                if reset_button:
                    try:
                        sheet = load_data('Users')
                        user_list = sheet.get_all_records()
                        for idx, row in enumerate(user_list, start=2):  # Google Sheets rows start at 2 (1 is header)
                            if row["Email"] == email_to_reset:
                                sheet.update_cell(idx, 2, "")  # Password is column 2
                                st.success(f"Password for {email_to_reset} has been reset.")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Failed to reset password: {e}")


    with tab3:
        tab3_col1, tab3_col2, tab3_col3 = st.columns(3)
        with tab3_col2:
            st.subheader("Delete User")

            with st.form("delete_user_form"):
                email_to_delete = st.selectbox("Select user to delete", users_df["Email"].values, key="delete_user")
                delete_button = st.form_submit_button("Delete User")

                if delete_button:
                    try:
                        sheet = load_data('Users')
                        user_list = sheet.get_all_records()
                        for idx, row in enumerate(user_list, start=2):  # Start from row 2 (after header)
                            if row["Email"] == email_to_delete:
                                sheet.delete_rows(idx)
                                st.success(f"User {email_to_delete} deleted.")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Failed to delete user: {e}")

