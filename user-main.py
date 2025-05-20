import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.express as px
import bcrypt
import time
from datetime import datetime, timedelta
import pytz

# --- Helper Functions ---
def get_shift_date(role):
    tz = pytz.timezone("Europe/London")
    now = datetime.now(tz)
    today = now.date()
    if "NS" in role:
        return today - timedelta(days=1) if now.time() < datetime.strptime("07:00", "%H:%M").time() else today
    return today

def convert_to_24_hour(time_str):
    return datetime.strptime(time_str, "%I.%M%p").strftime("%H:%M")

def load_df_users(sheet, email, shift_date, role_name):
    df = pd.DataFrame(sheet.get_all_records())
    return df[(df['Email'] == email) & 
              (df['task create Date'] == str(shift_date)) &
              (df['role'] == role_name)]

def load_tasks_for_role(gc, role_sheet_name, user_email, name_part, shift_date, role_name):
    role_sheet = gc.open("dailytaskDB").worksheet(role_sheet_name)
    task_rows = role_sheet.get_all_records()

    rows_to_append = []
    now_str = datetime.now(pytz.timezone("Europe/London")).strftime("%Y-%m-%d %H:%M:%S")

    for task in task_rows:
        rows_to_append.append([
            user_email,
            name_part,
            str(shift_date),
            "",  # task closed Date
            role_name,
            task['task'],
            False,  # done
            False,  # exempt
            "",     # exempt reason
            False,  # locked
            False,# missed
            task['time']
        ])
    
    target_ws = gc.open("dailytaskDB").worksheet("user-daily-task-test")
    target_ws.append_rows(rows_to_append)

def update_task(sheet, row_idx, done, exempt, reason):
    now = datetime.now(pytz.timezone("Europe/London")).strftime("%Y-%m-%d %H:%M:%S")
    missed = not done and not exempt
    sheet.update(range_name=f"G{row_idx+2}:K{row_idx+2}", values=[[done, exempt, reason, True, missed]])
    sheet.update_cell(row_idx + 2, 4, now)

def get_existing_role_for_today(sheet, email, shift_date):
    df = pd.DataFrame(sheet.get_all_records())
    existing = df[(df['Email'] == email) & 
                  (df['task create Date'] == str(shift_date))]
    if not existing.empty:
        return existing.iloc[0]['role']
    return None

# Function to delete a row based on the login match
def delete_row_by_login(sheet,login):
    # Get all data from the sheet
    rows = sheet.get_all_values()
    
    # Loop through rows and find the row where the login matches
    for i, row in enumerate(rows):
        if row[0] == login:  # Assuming login is in the first column (index 0)
            sheet.delete_rows(i + 1)  # +1 because rows are 1-indexed in Google Sheets
            st.cache_data.clear()
            return
    print(f"No row found with login '{login}'.")

@st.cache_data(show_spinner=False)
def load_users():
    sheet_users = dailytask_db.worksheet('Users')
    return pd.DataFrame(sheet_users.get_all_records())

@st.cache_data(ttl=60)
def load_tasks_daily(username):
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    return df[df['login'] == username]

def verify_password(plain_text_password, hashed_password):
    try:
        return bcrypt.checkpw(plain_text_password.encode(), hashed_password.encode())
    except:
        return False

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

st.set_page_config(page_title="LCY3 Operations Daily Task", layout="wide")

if "first_load" not in st.session_state:
    st.cache_data.clear()
    st.session_state.first_load = False

if "user_authenticated" not in st.session_state:
    st.session_state.user_authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "last_interaction" not in st.session_state:
    st.session_state.last_interaction = time.time()
# Initialize state variables only once
if "selected_temp_role" not in st.session_state:
    st.session_state.selected_temp_role = list(roles.keys())[0] 

timeout_seconds = 600
session_expired = time.time() - st.session_state.last_interaction > timeout_seconds

if session_expired:
    st.error("Session timed out due to inactivity.")
    st.info("Please click below to log in again.")
    if st.button("🔄 Login Again"):
        st.session_state.user_authenticated = False
        st.session_state.user_email = ""
        st.session_state.last_interaction = time.time()
        st.rerun()
    st.stop()

if st.session_state.user_authenticated:
    st.session_state.last_interaction = time.time()

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# Directly access Streamlit secrets and parse them as JSON
credentials_dict = st.secrets["thunder"] 
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(creds)
dailytask_db = client.open("dailytaskDB")
sheet = client.open("dailytaskDB").worksheet("Sheet1")

df_users = load_users()

# --- LOGIN LOGIC ---
if not st.session_state.get("user_authenticated", False):
    st.cache_data.clear()
    
    if "first_time_email" not in st.session_state:
        with st.form("Login", border=False):
            column1, column2, column3 = st.columns(3)
            with column2:
                st.title("User Dashboard Login")
                email = st.text_input("User Email").lower()
                password = st.text_input("Password", type="password")

                if st.form_submit_button("Login as User"):
                    user_row = df_users[
                        (df_users["Email"] == email) &
                        (df_users["Role"] == "user") &
                        (df_users["Status"] == "active")
                    ]

                    if not user_row.empty:
                        stored_password = user_row.iloc[0]["Password"]

                        if stored_password == "":
                            # First-time login
                            st.session_state["first_time_email"] = email
                            st.rerun()

                        elif bcrypt.checkpw(password.encode(), stored_password.encode()):
                            st.session_state.user_authenticated = True
                            st.session_state.user_email = email
                            st.success("User login successful.")
                            st.rerun()
                        else:
                            st.error("Invalid password.")
                    else:
                        st.error("Invalid user credentials or inactive account.")

    # --- First Time Password Setup ---
    else:
        st.warning("First-time login detected. Please create a new password.")

        with st.form("SetNewPasswordForm"):
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
                        creds = ServiceAccountCredentials.from_json_keyfile_name("daily-task.json", scope)
                        client = gspread.authorize(creds)
                        sheet = client.open("dailytaskDB").worksheet("Users")

                        user_list = sheet.get_all_records()
                        for idx, row in enumerate(user_list, start=2):  # row 2 because headers start at 1
                            if row["Email"].lower() == st.session_state["first_time_email"]:
                                sheet.update_cell(idx, 2, hashed_pw)  # Update Password (col 2)
                                st.success("Password set successfully. Please log in again.")
                                del st.session_state["first_time_email"]
                                st.cache_data.clear()
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error updating password: {e}")

# --- Dashboard ---
else:
    name_part = st.session_state.user_email.split("@")[0].capitalize()
    name_part_data = st.session_state.user_email.split("@")[0].lower()
    user_daily_task = load_tasks_daily(name_part_data)
    cols1, cols2, cols3, cols4 = st.columns([0.7,0.1, 0.1, 0.1])
    with cols1:
        st.title(f"Welcome {name_part}!")
    with cols3:
        if st.button("🔄 Reload"):
            load_users.clear()
            st.rerun()
    with cols4:
        if st.button("🚪 Logout"):
            st.session_state.user_authenticated = False
            st.session_state.user_email = ""
            st.session_state.clear()
            st.rerun()

    user_info = df_users[df_users["Email"] == st.session_state.user_email]
    if not user_info.empty:
        user_info = user_info.iloc[0]
        colz1,colz2 = st.columns([0.55, 0.45])
        with colz1:
            with st.form('Daily Task'):
                row1col1, smiley1, row1col2, smiley2 = st.columns([0.4, 0.1, 0.4, 0.1],)
                # "Do Later" Section
                with row1col1:
                    st.subheader("Do Later")
                    st.text_input(label="First Task", key="ab",label_visibility='hidden',value=user_daily_task.iloc[0]['task 1'] if not user_daily_task.empty else "")
                    st.text_input(label="Second Task", key="tb",label_visibility='hidden',value=user_daily_task.iloc[0]['task 2'] if not user_daily_task.empty else "")
                    st.text_input(label="Third Task", key="trb",label_visibility='hidden',value=user_daily_task.iloc[0]['task 3'] if not user_daily_task.empty else "")
                    st.text_input(label="Fourth Task", key="tbr",label_visibility='hidden',value=user_daily_task.iloc[0]['task 4'] if not user_daily_task.empty else "")
                with smiley1:
                    st.subheader("")  # spacing
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], key='fdf',label_visibility='hidden',index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 1 emoji']) if not user_daily_task.empty else 0,)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱',''], label_visibility='hidden', key='fefeg',index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 2 emoji']) if not user_daily_task.empty else 0,)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='fegegece',index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 3 emoji']) if not user_daily_task.empty else 0,)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱',''], label_visibility='hidden', key='wscef', index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 4 emoji']) if not user_daily_task.empty else 0,)

                with row1col1:    
                    st.subheader("Avoid")
                    st.text_input(label="First Task", key="etb",label_visibility='hidden',value=user_daily_task.iloc[0]['task 5'] if not user_daily_task.empty else "")
                    st.text_input(label="Second Task", key="gtb",label_visibility='hidden', value=user_daily_task.iloc[0]['task 6'] if not user_daily_task.empty else "")
                    st.text_input(label="Third Task", key="tytb",label_visibility='hidden', value=user_daily_task.iloc[0]['task 7'] if not user_daily_task.empty else "")
                    st.text_input(label="Fourth Task", key="terb",label_visibility='hidden', value=user_daily_task.iloc[0]['task 8'] if not user_daily_task.empty else "")

                with smiley1:    
                    st.subheader("")  # spacing
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm1',index=['🐸','😊','🐶','🐱',''].index(user_daily_task.iloc[0]['task 5 emoji']) if not user_daily_task.empty else 0)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm2',index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 6 emoji']) if not user_daily_task.empty else 0)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm3', index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 7 emoji']) if not user_daily_task.empty else 0)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm4', index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 8 emoji']) if not user_daily_task.empty else 0)

                # "Do First" Section
                with row1col2:
                    st.subheader("Do First")
                    st.text_input(label="First Task", key="tfb",label_visibility='hidden',value=user_daily_task.iloc[0]['task 9'] if not user_daily_task.empty else "")
                    st.text_input(label="Second Task", key="tbe",label_visibility='hidden',value=user_daily_task.iloc[0]['task 10'] if not user_daily_task.empty else "")
                    st.text_input(label="Third Task", key="twb",label_visibility='hidden',value=user_daily_task.iloc[0]['task 11'] if not user_daily_task.empty else "")
                    st.text_input(label="Fourth Task", key="tbi",label_visibility='hidden',value=user_daily_task.iloc[0]['task 12'] if not user_daily_task.empty else "")
                    
                    st.subheader("Delegate")
                    st.text_input(label="First Task", key="wetb",label_visibility='hidden',value=user_daily_task.iloc[0]['task 13'] if not user_daily_task.empty else "")
                    st.text_input(label="Second Task", key="twbb",label_visibility='hidden',value=user_daily_task.iloc[0]['task 14'] if not user_daily_task.empty else "")
                    st.text_input(label="Third Task", key="twerb",label_visibility='hidden',value=user_daily_task.iloc[0]['task 15'] if not user_daily_task.empty else "")
                    st.text_input(label="Fourth Task", key="tbrer",label_visibility='hidden',value=user_daily_task.iloc[0]['task 16'] if not user_daily_task.empty else "")

                with smiley2:
                    st.subheader("")  # spacing
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm5',index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 9 emoji']) if not user_daily_task.empty else 0)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm6',index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 10 emoji']) if not user_daily_task.empty else 0)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm7',index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 11 emoji']) if not user_daily_task.empty else 0)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm8',index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 12 emoji']) if not user_daily_task.empty else 0)
                    
                    st.subheader("")  # spacing
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm9',index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 13 emoji']) if not user_daily_task.empty else 0)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm10',index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 14 emoji']) if not user_daily_task.empty else 0)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm11', index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 15 emoji']) if not user_daily_task.empty else 0)
                    st.selectbox('Select a smiley', options=['','🐸','😊','🐶','🐱'], label_visibility='hidden', key='sm12', index=['🐸','😊','🐶','🐱'].index(user_daily_task.iloc[0]['task 16 emoji']) if not user_daily_task.empty else 0)
                    
                # Change submit button text if tasks exist
                submit_button_label = "Update Task" if not df_users.empty else "Add Task"
                submit = st.form_submit_button(submit_button_label)

                if submit:
                    # Get today's date
                    today = datetime.now().strftime("%Y-%m-%d")

                    # Prepare data in the order of the sheet's columns
                    task_data = list(map(str, [
                        name_part_data,
                        today,
                        "",  # role column
                        st.session_state.ab,
                        st.session_state.tb,
                        st.session_state.trb,
                        st.session_state.tbr,
                        st.session_state.etb,
                        st.session_state.gtb,
                        st.session_state.tytb,
                        st.session_state.terb,
                        st.session_state.tfb,
                        st.session_state.tbe,
                        st.session_state.twb,
                        st.session_state.tbi,
                        st.session_state.wetb,
                        st.session_state.twbb,
                        st.session_state.twerb,
                        st.session_state.tbrer,
                        st.session_state.fdf,
                        st.session_state.fefeg,
                        st.session_state.fegegece,
                        st.session_state.wscef,
                        st.session_state.sm1,
                        st.session_state.sm2,
                        st.session_state.sm3,
                        st.session_state.sm4,
                        st.session_state.sm5,
                        st.session_state.sm6,
                        st.session_state.sm7,
                        st.session_state.sm8,
                        st.session_state.sm9,
                        st.session_state.sm10,
                        st.session_state.sm11,
                        st.session_state.sm12
                    ]))
                    
                    if submit_button_label == 'Add Task':
                        try:
                            sheet.append_row(task_data)
                            st.toast("✅ Task successfully added to the sheet!", icon="🎉")
                        except Exception as e:
                            st.toast(f"❌ Failed to upload task. Error: {e}", icon="⚠️")
                    else:
                        try:
                            delete_row_by_login(sheet=sheet,login=name_part_data)
                            sheet.append_row(task_data)
                            st.toast("✅ Task successfully added to the sheet!", icon="🎉")
                        except Exception as e:
                            st.toast(f"❌ Failed to upload task. Error: {e}", icon="⚠️")

        with colz2:
            with st.container(height= 1000, border=True):
                # Initialize session state if not present
                if "selected_role" not in st.session_state:
                    st.session_state.selected_role = None

                # Determine today's shift date
                shift_date = get_shift_date(user_info['role'])

                # Get task sheet and existing role
                task_sheet = dailytask_db.worksheet("user-daily-task-test")
                existing_role_code = get_existing_role_for_today(task_sheet, user_info["Email"], shift_date)

                if existing_role_code:
                    # Display the role if already assigned in the DB
                    role_display = next((k for k, v in roles.items() if v == existing_role_code), existing_role_code)
                    st.session_state.selected_role = role_display
                    st.info(f"✅ Loaded existing role: **{role_display}** for today.")

                elif st.session_state.selected_role:
                    # Role already selected in current session
                    st.success(f"✅ Role already selected: **{st.session_state.selected_role}**")

                else:
                    # Allow user to select and confirm a role inside a form
                    st.subheader("Select Your Role")

                    with st.form(key="role_selection_form"):
                        selected_temp_role = st.selectbox(
                            "Choose your role",
                            list(roles.keys()),
                            key="selected_temp_role_form"  # Changed to avoid key collision
                        )
                        
                        submitted = st.form_submit_button("✅ Confirm Role")
                        
                        if submitted:
                            st.session_state.selected_role = selected_temp_role
                            st.success(f"Role '{selected_temp_role}' selected and locked for today.")
                            st.rerun()  # <- This reloads the app to hide the form


                if st.session_state.selected_role:
                    role = st.session_state.selected_role
                    is_night_shift = "NS" in roles[role]
                    # Continue with loading tasks using `role`
                    shift_date = get_shift_date(user_info['role'])
                    tasks_df = load_df_users(task_sheet, user_info["Email"], shift_date, roles[role])
                    tz = pytz.timezone("Europe/London")
                    now = datetime.now(tz)

                    if tasks_df.empty:
                        load_tasks_for_role(client, roles[role], user_info["Email"], name_part, shift_date, roles[role])
                        tasks_df = load_df_users(task_sheet, user_info["Email"], shift_date, roles[role])
                        tz = pytz.timezone("Europe/London")
                        now = datetime.now(tz)      
                        st.success("Today's tasks loaded!")

                    # ... Continue task display logic
                    st.subheader(f"Tasks for {shift_date}")
                    
                    # Boolean mapping
                    bool_map = {'TRUE': True, 'FALSE': False}

                    # Convert relevant columns before iteration
                    for col in ["done", "exempt", "locked", "missed"]:
                        tasks_df[col] = tasks_df[col].map(bool_map)
                    # Add full datetime column for sorting
                    task_datetimes = []
                    task_status = []  # 0 = upcoming/editable, 1 = past/locked/missed

                    for i, row in tasks_df.iterrows():
                        due_time_str = row['due time']
                        try:
                            task_time = datetime.strptime(due_time_str, "%I.%M%p").time()
                            task_hour = task_time.hour + task_time.minute / 60.0

                            if is_night_shift:
                                if 0 <= task_hour < 7:
                                    task_day = shift_date + timedelta(days=1)
                                else:
                                    task_day = shift_date
                            else:
                                task_day = shift_date

                            full_dt = tz.localize(datetime.combine(task_day, task_time))
                        except Exception:
                            full_dt = datetime.max.replace(tzinfo=tz)  # fallback to max so it's pushed to bottom

                        task_datetimes.append(full_dt)

                        # Determine if it's a past/locked task (push to bottom)
                        past_locked = full_dt < now or row.get("locked", False)
                        task_status.append(int(past_locked))

                    # Add to DataFrame
                    tasks_df['task_datetime'] = task_datetimes
                    tasks_df['past_locked'] = task_status

                    # Sort: first by 'past_locked' (0s first), then by 'task_datetime' ascending
                    tasks_df = tasks_df.sort_values(by=["past_locked", "task_datetime"], ascending=[True, True])

                    # Ensures all values are boolean before looping
                    for i, row in tasks_df.iterrows():
                    
                        with st.container(border=True):  # Iterating correctly over DataFrame
                            task_id = f"{i}_{row['task']}_{row['task create Date']}"

                            tz = pytz.timezone("Europe/London")
                            now = datetime.now(tz)

                            due_time_str = row['due time']
                            try:
                                task_time = datetime.strptime(due_time_str, "%I.%M%p").time()
                                task_hour = task_time.hour + task_time.minute / 60.0
                                if is_night_shift:
                                    # Night shift spans from 19:30 of current day to ~06:59 next day
                                    if 0 <= task_hour < 7:  # Early morning (e.g., 2:00AM next day of night shift)
                                        task_day = shift_date + timedelta(days=1)
                                    else:
                                        task_day = shift_date
                                else:
                                    task_day = shift_date

                                task_datetime = tz.localize(datetime.combine(task_day, task_time))
                                is_editable = now < task_datetime and not row.get("locked", False)

                            except ValueError:
                                # Handle invalid time format
                                task_datetime = None
                                is_editable = False

                                # Automatically lock and mark missed tasks after due time if neither done nor exempt
                                if now > task_datetime and not row.get("locked", False):
                                    missed = not row.get("done", False) and not row.get("exempt", False)
                                    if missed:
                                        st.warning(f"⚠️ Task missed: {row['task']}")
                                    # Update sheet only if missed or overdue
                                    update_task(task_sheet, i, row.get("done", False), row.get("exempt", False), row.get("exempt reason", ""))

                            except ValueError:
                                # If time parsing fails, fall back to locked status
                                is_editable = not row.get("locked", False)


                            # Convert 'due time' string (e.g., '8.00AM') to 24-hour format (e.g., '08:00')
                            due_time_str = row['due time']
                            try:
                                due_time_obj = datetime.strptime(due_time_str, "%I.%M%p")
                                due_time_24hr = due_time_obj.strftime("%H:%M")
                            except ValueError:
                                due_time_24hr = due_time_str  # fallback to original if parsing fails

                            col1, col2, col3 = st.columns([3, 1, 1])
                            with col1:
                                st.markdown(
                                    f'<div class="task-container"><h5>{row["task"]}</h5><p>{row["task create Date"]}</p><p>{due_time_24hr}</p></div>',
                                    unsafe_allow_html=True,
                                )

                            if is_editable:  # Corrected logic
                                with col2:
                                    done = st.checkbox("Done", value=row.get("done", False), key=f"done_{task_id}")
                                with col3:
                                    exempt = st.checkbox("Exempt", value=row.get("exempt", False), key=f"exempt_{task_id}")

                                reason = ""
                                if exempt:
                                    reason = st.text_input("Exempt Reason", value=row.get("exempt reason", ""), key=f"reason_{task_id}")

                                both_selected = done and exempt
                                neither_selected = not done and not exempt
                                can_save = not both_selected and not neither_selected

                                if both_selected:
                                    st.error("❌ You cannot select both Done and Exempt.")
                                elif neither_selected:
                                    st.info("☝️ Please mark as either Done or Exempt to proceed.")

                                if can_save:
                                    if st.button("Save", key=f"save_{task_id}"):
                                        update_task(task_sheet, i, done, exempt, reason)
                                        print(i + 2)
                                        st.success("✅ Task updated and locked.")
                                        st.rerun()
                            else:
                                if (row["locked"] == True) and (row["done"] == True):
                                    st.success("✅ Task has been marked and locked.")
                                elif (row["locked"] == True) and (row["exempt"] == True):
                                    st.success("⚠️ Task has been exempted with reason.")
                                else:
                                    st.warning('❌ Task missed and is no longer editable')
