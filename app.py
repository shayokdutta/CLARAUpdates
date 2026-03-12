import streamlit as st
import pandas as pd
import cv2
import os
import time

# 1. Page Configuration
st.set_page_config(page_title="Behavioral Analyzer", layout="wide")

st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 1rem;
        }
        
        /* Make the default (secondary) button Green inside the dialog */
        div[data-testid="stDialog"] button[kind="secondary"] {
            background-color: #2e7d32 !important;
            color: white !important;
            border-color: #2e7d32 !important;
        }
        
        /* Make the primary button Red inside the dialog */
        div[data-testid="stDialog"] button[kind="primary"] {
            background-color: #d32f2f !important;
            color: white !important;
            border-color: #d32f2f !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🐁 Neural Behavioral Analyzer")

# ==========================================
# 2. State Management Initialization
# ==========================================
if 'frame_number' not in st.session_state: st.session_state.frame_number = 0
if 'display_height' not in st.session_state: st.session_state.display_height = 300
if 'is_playing' not in st.session_state: st.session_state.is_playing = False

if 'current_video' not in st.session_state: st.session_state.current_video = None
if 'current_session' not in st.session_state: st.session_state.current_session = None
if 'last_vid_date' not in st.session_state: st.session_state.last_vid_date = None
if 'video_outcomes' not in st.session_state: st.session_state.video_outcomes = {} 
if 'animal_id' not in st.session_state: st.session_state.animal_id = ""
if 'current_folder' not in st.session_state: st.session_state.current_folder = "."

# ==========================================
# 3. Core Functions & Callbacks
# ==========================================
def switch_to_video(new_vid):
    parts = new_vid.split('_')
    new_session = parts[2] if len(parts) >= 3 else "unknown"
    vid_date = parts[1] if len(parts) >= 3 else "000000"
    
    if st.session_state.current_session and new_session != st.session_state.current_session:
        st.session_state.video_outcomes = {}
        st.session_state.animal_id = ""
        
    st.session_state.current_video = new_vid
    st.session_state.current_session = new_session
    st.session_state.last_vid_date = vid_date
    st.session_state.frame_number = 0
    st.session_state.is_playing = False
    st.session_state.video_selector = new_vid

# --- NEW: Callback to process the uploaded file ---
def process_uploaded_file(uploaded_file, vid_files):
    try:
        df_loaded = pd.read_csv(uploaded_file)
        if "Video" in df_loaded.columns and "Outcome" in df_loaded.columns:
            st.session_state.video_outcomes = dict(zip(df_loaded["Video"], df_loaded["Outcome"]))
            
            # Extract Animal ID from the filename (e.g., 251125_Mouse12_behaviorCounts.csv -> Mouse12)
            file_name = uploaded_file.name
            if "_behaviorCounts.csv" in file_name:
                prefix = file_name.replace("_behaviorCounts.csv", "")
                parts = prefix.split("_", 1) # Splits only on the very first underscore
                if len(parts) > 1:
                    st.session_state.animal_id = parts[1]
            
            first_video_in_session = df_loaded["Video"].iloc[0]
            if first_video_in_session in vid_files:
                switch_to_video(first_video_in_session)
    except Exception as e:
        print(f"Error loading file: {e}")

@st.dialog("💾 Session Complete: Save Data")
def save_session_dialog(intended_vid):
    st.warning(f"You are attempting to switch to a new session. Please save the data for **{st.session_state.current_session}** first.")
    
    date_str = st.session_state.last_vid_date
    yymmdd = date_str[2:] if len(date_str) == 8 else date_str 
    anim_id = st.session_state.animal_id.strip() if st.session_state.animal_id.strip() else "UnknownID"
    
    filename = f"{yymmdd}_{anim_id}_behaviorCounts.csv"
    save_path = os.path.join(st.session_state.current_folder, filename)
    
    succ = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Success')
    fail = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Fail')
    att = succ + fail
    rate = (succ / att * 100) if att > 0 else 0.0
    
    df_save = pd.DataFrame(list(st.session_state.video_outcomes.items()), columns=["Video", "Outcome"])
    df_save["Total_Attempts"] = att
    df_save["Total_Success"] = succ
    df_save["Total_Fail"] = fail
    df_save["Success_Rate_%"] = round(rate, 1)
    
    csv_data = df_save.to_csv(index=False)
    file_exists = os.path.exists(save_path)
    
    if file_exists:
        st.error(f"⚠️ **Warning:** The file `{filename}` already exists in this folder.")
        confirm_overwrite = st.checkbox("I confirm I want to overwrite the existing file.")
        disable_save = not confirm_overwrite
        btn_label = f"⚠️ Overwrite '{filename}' & Switch"
    else:
        disable_save = False
        btn_label = f"💾 Save '{filename}' to Video Folder & Switch"

    if st.button(btn_label, use_container_width=True, disabled=disable_save):
        try:
            with open(save_path, "w") as f:
                f.write(csv_data)
            switch_to_video(intended_vid)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to save file. Error: {e}")
    
    st.markdown("---")
    if st.button("🗑️ Discard Data & Switch Anyway", type="primary", use_container_width=True, on_click=switch_to_video, args=(intended_vid,)):
        st.rerun()

def handle_radio_change():
    new_vid = st.session_state.video_selector
    if not new_vid or new_vid == st.session_state.current_video: return
    
    parts = new_vid.split('_')
    new_session = parts[2] if len(parts) >= 3 else "unknown"
    
    if st.session_state.current_session and new_session != st.session_state.current_session:
        st.session_state.video_selector = st.session_state.current_video
        save_session_dialog(new_vid)
    else:
        switch_to_video(new_vid)

def classify_and_advance(outcome, video_files):
    current_vid = st.session_state.current_video
    st.session_state.video_outcomes[current_vid] = outcome
    
    try:
        curr_idx = video_files.index(current_vid)
        if curr_idx < len(video_files) - 1:
            next_vid = video_files[curr_idx + 1]
            curr_session = st.session_state.current_session
            parts = next_vid.split('_')
            next_session = parts[2] if len(parts) >= 3 else "unknown"
            if curr_session == next_session:
                switch_to_video(next_vid)
    except ValueError:
        pass 

# Playback Callbacks
def next_frame(total_frames):
    if st.session_state.frame_number < total_frames - 1: st.session_state.frame_number += 1
def prev_frame():
    if st.session_state.frame_number > 0: st.session_state.frame_number -= 1
def sync_jump(): st.session_state.frame_number = st.session_state.jump_input
def sync_slider(): st.session_state.frame_number = st.session_state.slider_frame
def toggle_play(): st.session_state.is_playing = not st.session_state.is_playing

# ==========================================
# 4. Main App Layout
# ==========================================
folder_path = st.text_input("📁 Enter the absolute path to your video folder:", value=".")
st.session_state.current_folder = folder_path 

if os.path.exists(folder_path) and os.path.isdir(folder_path):
    supported_exts = ('.mp4', '.mkv', '.mov', '.avi')
    video_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(supported_exts)])

    if video_files:
        if st.session_state.current_video not in video_files:
            switch_to_video(video_files[0])

        col_video, col_data, col_playlist = st.columns([4, 2.5, 2])
        
        with col_playlist:
            st.subheader("📋 Playlist")
            st.radio("Select a video", video_files, key="video_selector", on_change=handle_radio_change, label_visibility="collapsed")
        
        # ==========================================
        # DATA ENTRY COLUMN (MIDDLE)
        # ==========================================
        with col_data:
            st.subheader("📝 Session Data")
            
            # --- UPDATED: Explicit File Uploader for Resuming ---
            uploaded_file = st.file_uploader("📥 Upload CSV to Resume Data", type=['csv'])
            if uploaded_file is not None:
                st.button("🔄 Load Uploaded Data", use_container_width=True, on_click=process_uploaded_file, args=(uploaded_file, video_files))
            
            st.session_state.animal_id = st.text_input("Animal ID:", value=st.session_state.animal_id, placeholder="e.g. Mouse_12")
            st.markdown(f"**Current Session:** `{st.session_state.current_session}`")
            st.markdown("---")
            
            current_status = st.session_state.video_outcomes.get(st.session_state.current_video, "Unclassified")
            status_colors = {
                "Success": "🟢 **Success**",
                "Fail": "🔴 **Fail**",
                "Ignore": "⚪ **Ignored**",
                "Unclassified": "🟡 **Unclassified**"
            }
            st.markdown(f"Current Video Status: {status_colors.get(current_status)}")
            
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            btn_col1.button("✅ Success", use_container_width=True, on_click=classify_and_advance, args=('Success', video_files))
            btn_col2.button("❌ Fail", use_container_width=True, on_click=classify_and_advance, args=('Fail', video_files))
            btn_col3.button("🚫 Ignore", use_container_width=True, on_click=classify_and_advance, args=('Ignore', video_files))
            
            succ = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Success')
            fail = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Fail')
            att = succ + fail 
            rate = (succ / att * 100) if att > 0 else 0.0
            
            df_summary = pd.DataFrame([{"Attempt": att, "Success": succ, "Fail": fail, "Success Rate": f"{rate:.1f}%"}])
            st.markdown("<br>**Session Summary:**", unsafe_allow_html=True)
            st.dataframe(df_summary, hide_index=True, use_container_width=True)

            st.markdown("**Editable Raw Data:**", help="Double-click any cell in the Outcome column to manually fix errors.")
            if st.session_state.video_outcomes:
                df_raw = pd.DataFrame(list(st.session_state.video_outcomes.items()), columns=["Video", "Outcome"])
                
                edited_df = st.data_editor(
                    df_raw, 
                    use_container_width=True, 
                    hide_index=True,
                    disabled=["Video"] 
                )
                
                new_outcomes = dict(zip(edited_df["Video"], edited_df["Outcome"]))
                if new_outcomes != st.session_state.video_outcomes:
                    st.session_state.video_outcomes = new_outcomes
                    st.rerun()

            # --- NEW: Manual Download/Save Button ---
            st.markdown("---")
            st.markdown("**Manual Export:**")
            
            date_str = st.session_state.last_vid_date if st.session_state.last_vid_date else "000000"
            yymmdd = date_str[2:] if len(date_str) == 8 else date_str 
            anim_id = st.session_state.animal_id.strip() if st.session_state.animal_id.strip() else "UnknownID"
            manual_filename = f"{yymmdd}_{anim_id}_behaviorCounts.csv"
            
            df_manual_save = pd.DataFrame(list(st.session_state.video_outcomes.items()), columns=["Video", "Outcome"])
            df_manual_save["Total_Attempts"] = att
            df_manual_save["Total_Success"] = succ
            df_manual_save["Total_Fail"] = fail
            df_manual_save["Success_Rate_%"] = round(rate, 1)
            manual_csv_data = df_manual_save.to_csv(index=False)
            
            st.download_button(
                label="💾 Download Current Session to Save",
                data=manual_csv_data,
                file_name=manual_filename,
                mime="text/csv",
                use_container_width=True
            )

        # ==========================================
        # VIDEO PLAYER COLUMN (LEFT)
        # ==========================================
        with col_video:
            active_vid = st.session_state.current_video
            if active_vid:
                st.subheader(f"📺 {active_vid}")
                video_path = os.path.join(folder_path, active_vid)
                
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    
                    st.write(f"**Total Frames:** {total_frames} | **Playback:** 10 FPS")

                    cap.set(cv2.CAP_PROP_POS_FRAMES, st.session_state.frame_number)
                    ret, frame = cap.read()
                    
                    if ret:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        st.slider("🔍 Adjust Video Display Height", min_value=100, max_value=1080, step=50, key="display_height")
                        
                        h, w, _ = frame_rgb.shape
                        aspect_ratio = w / h
                        calc_width = int(st.session_state.display_height * aspect_ratio)
                        
                        st.image(frame_rgb, width=calc_width)
                    else:
                        st.error("Could not read frame.")
                        
                    cap.release()

                    st.markdown("---")

                    st.session_state.slider_frame = st.session_state.frame_number
                    st.session_state.jump_input = st.session_state.frame_number

                    col_play, col_prev, col_input, col_next = st.columns([1, 1, 3, 1])
                    
                    with col_play:
                        play_label = "⏸️ Pause" if st.session_state.is_playing else "▶️ Play"
                        st.button(play_label, on_click=toggle_play, use_container_width=True)

                    with col_prev:
                        st.button("⬅️ Prev", on_click=prev_frame, use_container_width=True)
                            
                    with col_input:
                        st.slider("Scrub Frames", min_value=0, max_value=max(0, total_frames - 1), key="slider_frame", on_change=sync_slider, label_visibility="collapsed")
                            
                    with col_next:
                        st.button("Next ➡️", on_click=next_frame, args=(total_frames,), use_container_width=True)

                    st.number_input("Jump to exact frame:", min_value=0, max_value=max(0, total_frames - 1), step=1, key="jump_input", on_change=sync_jump)

                    if st.session_state.is_playing:
                        if st.session_state.frame_number < total_frames - 1:
                            time.sleep(0.1) 
                            st.session_state.frame_number += 1
                            st.rerun()       
                        else:
                            st.session_state.is_playing = False 
                            st.rerun()
                else:
                    st.error("Failed to open video with OpenCV.")
    else:
        st.warning("No supported video files found.")
else:
    st.error("Please enter a valid folder path.")