import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
import bcrypt

st.set_page_config(page_title="Daily Task Admin",layout='wide')

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

# --- ADMIN LOGIN LOGIC ---
if not st.session_state.get("authenticated", False):
    st.cache_data.clear()

    if "first_time_email" not in st.session_state:
        login_column_1, login_column_2, login_column_3 = st.columns(3)
        with login_column_2:
            st.title("Admin Login")

            with st.form("login_form"):
                email = st.text_input("Email").lower()
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")

                if submitted:
                    user_row = users_df[
                        (users_df["Email"] == email) &
                        (users_df["Role"].str.lower() == "admin") &
                        (users_df["Status"].str.lower() == "active")
                    ]

                    if not user_row.empty:
                        stored_password = user_row.iloc[0]["Password"]

                        if stored_password == "":
                            # First-time login detected
                            st.session_state["first_time_email"] = email
                            st.rerun()
                        elif bcrypt.checkpw(password.encode(), stored_password.encode()):
                            st.session_state.authenticated = True
                            st.session_state.user_role = "admin"
                            st.session_state.user_email = email
                            st.toast("Login successful!")
                            st.rerun()
                        else:
                            st.error("Invalid password.")
                    else:
                        st.error("Invalid credentials or inactive account.")
    else:
        # First-time password setup
        st.warning("First-time login detected. Please create a new password.")

        with st.form("SetNewAdminPasswordForm"):
            new_pass = st.text_input("New Password", type="password", key="new_pass")
            confirm_pass = st.text_input("Confirm New Password", type="password", key="confirm_pass")

            if st.form_submit_button("Set New Password"):
                if new_pass != confirm_pass:
                    st.error("Passwords do not match.")
                elif len(new_pass) < 6:
                    st.error("Password too short. Minimum 6 characters.")
                else:
                    hashed_pw = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()

                    try:
                        # Update Google Sheet
                        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                        # Directly access Streamlit secrets and parse them as JSON
                        credentials_dict = st.secrets["thunder"] 
                        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
                        client = gspread.authorize(creds)
                        sheet = client.open("dailytaskDB").worksheet("Users")

                        user_list = sheet.get_all_records()
                        for idx, row in enumerate(user_list, start=2):  # start at 2 to skip header
                            if row["Email"].lower() == st.session_state["first_time_email"]:
                                sheet.update_cell(idx, 2, hashed_pw)  # Update password (col 2)
                                st.success("Password set successfully. Please log in again.")
                                del st.session_state["first_time_email"]
                                st.cache_data.clear()
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error updating password: {e}")

    st.stop()


# Main dashboard
st.info('Test phase for project @LCY3. Page is under active changes!. Do not share access!. Access is granted only by admin @kmicalex. Reach out to @kmicalex for feedbacks, suggestions and comments.',icon="ℹ️")
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

    # st.subheader("Department Breakdown")
    # st.bar_chart(users_df['Department'].value_counts())

    # st.subheader("Shift Start Time Distribution")
    # shift_start_counts = users_df['Start Time'].value_counts().sort_index()
    # st.line_chart(shift_start_counts)


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
                                sheet.update_cell(idx, 2, "")  # Reset Password (Column 2)
                                st.success(f"Password for {email_to_reset} has been reset.")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Failed to reset password: {e}")

        with tab2_col1:
            st.subheader("Set User Status")

            with st.form("set_status_form"):
                email_to_update = st.selectbox("Select user to update status", users_df["Email"].values, key="status_user")
                new_status = st.selectbox("Set status", ["active", "inactive"], key="new_status")
                update_status_button = st.form_submit_button("Update Status")

                if update_status_button:
                    try:
                        sheet = load_data('Users')
                        user_list = sheet.get_all_records()
                        for idx, row in enumerate(user_list, start=2):  # Google Sheets rows start at 2 (1 is header)
                            if row["Email"] == email_to_update:
                                sheet.update_cell(idx, 4, new_status)  # Assuming Status is column 3
                                st.success(f"Status for {email_to_update} updated to {new_status}.")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Failed to update status: {e}")


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

with tab_3:
    tab3_col1, tab3_col2, tab3_col3 = st.columns(3)
    with tab3_col2:
        st.subheader("View Role-Based Task Sheet")

        roles = {
            "Operations Manager Inbound Night Shift": "OM-IB-NS",
            "Operations Manager Inbound Day Shift": "OM-IB-DS",
            "Operations Manager Outbound Night Shift": "OM-OB-NS",
            "Operations Manager Outbound Day Shift": "OM-OB-DS",
            "Area Manager Inbound Night Shift": "AM-IB-NS",
            "Area Manager Inbound Day Shift": "AM-IB-DS",
            "Area Manager Outbound Night Shift": "AM-OB-NS",
            "Area Manager Outbound Day Shift": "AM-OB-DS",
        }


        with st.form("role_data_form"):
            selected_role_display = st.selectbox("Select Role", list(roles.keys()))
            action = st.radio("Action", ["Fetch", "Save"], horizontal=True, key="form_action", label_visibility="collapsed")
            submit = st.form_submit_button("Submit")

        if submit:
            sheet_name = roles[selected_role_display]
            sheet = load_data(sheet_name)

            if st.session_state.form_action == "Fetch":
                data = sheet.get_all_records()
                if not data:
                    st.warning("The selected sheet is currently empty.")
                else:
                    df = pd.DataFrame(data)
                    st.session_state.df_original = df.copy()
                    
                    # Keep task and time columns
                    st.session_state.df_edited = df[["task", "time"]].copy()
                    st.success("Data fetched. You can now edit and then choose 'Save' to store changes.")


            # Action: Save
            elif st.session_state.form_action == "Save":
                if "df_original" in st.session_state and "df_edited" in st.session_state:
                    original_df = st.session_state.df_original
                    edited_df = st.session_state.df_edited
                    updates_made = False

                    for idx in range(len(edited_df)):
                        new_task = edited_df.loc[idx, "task"]
                        new_time = edited_df.loc[idx, "time"]
                        old_task = original_df.loc[idx, "task"]
                        old_time = original_df.loc[idx, "time"]

                        # Update task if changed
                        if new_task != old_task:
                            sheet.update_cell(idx + 2, original_df.columns.get_loc("task") + 1, new_task)
                            updates_made = True

                        # Update time if changed
                        if new_time != old_time:
                            sheet.update_cell(idx + 2, original_df.columns.get_loc("time") + 1, new_time)
                            updates_made = True

                    if updates_made:
                        st.success("Tasks and/or time updated successfully in the sheet.")
                    else:
                        st.info("No changes detected.")
                else:
                    st.error("No data to save. Please fetch data first.")


        # Always show editor if data is available
        if "df_edited" in st.session_state:
            st.write("🛠️ Edit the **Task** column below. After editing, choose 'Save' and click Submit.")
            edited_df = st.data_editor(
                st.session_state.df_edited,
                num_rows="dynamic",
                use_container_width=True,
                key="task_editor"
            )
            st.session_state.df_edited = edited_df  # Persist changes

