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
    </style>
""", unsafe_allow_html=True)
st.title("🐁 Neural Behavioral Analyzer")

# ==========================================
# 2. State Management & Dialogs
# ==========================================
if 'frame_number' not in st.session_state: st.session_state.frame_number = 0
if 'display_height' not in st.session_state: st.session_state.display_height = 300
if 'is_playing' not in st.session_state: st.session_state.is_playing = False
if 'current_video' not in st.session_state: st.session_state.current_video = None

# --- UPDATED: Per-Video State Tracking ---
if 'current_session' not in st.session_state: st.session_state.current_session = None
if 'last_vid_date' not in st.session_state: st.session_state.last_vid_date = None
if 'video_outcomes' not in st.session_state: st.session_state.video_outcomes = {} # Tracks {filename: 'Success'/'Fail'/'Ignore'}
if 'animal_id' not in st.session_state: st.session_state.animal_id = ""
if 'show_save_dialog' not in st.session_state: st.session_state.show_save_dialog = False
if 'pending_save' not in st.session_state: st.session_state.pending_save = None

# Save Popup Dialog
@st.dialog("💾 Session Complete: Save Data")
def save_session_dialog():
    data = st.session_state.pending_save
    st.warning(f"You switched to a new session. Please save the data for **{data['session']}**.")
    
    att = data['counts']['attempts']
    succ = data['counts']['success']
    fail = data['counts']['fail']
    rate = (succ / att) if att > 0 else 0.0
    
    # Format the filename: YYMMDD_animalID_behaviorCounts.csv
    date_str = data['date']
    yymmdd = date_str[2:] if len(date_str) == 8 else date_str 
    anim_id = data['animal_id'].strip() if data['animal_id'].strip() else "UnknownID"
    
    filename = f"{yymmdd}_{anim_id}_behaviorCounts.csv"
    csv_data = f"Attempt,Success,Fail,Success Rate\n{att},{succ},{fail},{rate:.2f}\n"
    
    st.download_button(
        label=f"⬇️ Download {filename}", 
        data=csv_data, 
        file_name=filename, 
        mime="text/csv",
        use_container_width=True
    )
    
    if st.button("Dismiss / Continue", use_container_width=True):
        st.session_state.show_save_dialog = False
        st.rerun()

if st.session_state.show_save_dialog:
    save_session_dialog()

# Callbacks
def next_frame(total_frames):
    if st.session_state.frame_number < total_frames - 1: st.session_state.frame_number += 1
def prev_frame():
    if st.session_state.frame_number > 0: st.session_state.frame_number -= 1
def sync_jump(): st.session_state.frame_number = st.session_state.jump_input
def sync_slider(): st.session_state.frame_number = st.session_state.slider_frame
def toggle_play(): st.session_state.is_playing = not st.session_state.is_playing

# ==========================================
# 3. Main App Layout
# ==========================================
folder_path = st.text_input("📁 Enter the absolute path to your video folder:", value=".")

if os.path.exists(folder_path) and os.path.isdir(folder_path):
    supported_exts = ('.mp4', '.mkv', '.mov', '.avi')
    video_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(supported_exts)])

    if video_files:
        col_video, col_data, col_playlist = st.columns([4, 2.5, 2])
        
        with col_playlist:
            st.subheader("📋 Playlist")
            selected_video = st.radio("Select a video", video_files, label_visibility="collapsed")
            
            # --- SESSION DETECTION LOGIC ---
            if selected_video != st.session_state.current_video:
                parts = selected_video.split('_')
                vid_date = parts[1] if len(parts) >= 3 else "000000"
                vid_session = parts[2] if len(parts) >= 3 else "unknown"
                
                if st.session_state.current_session and vid_session != st.session_state.current_session:
                    # Calculate final stats from the dictionary
                    s_count = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Success')
                    f_count = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Fail')
                    
                    st.session_state.pending_save = {
                        'session': st.session_state.current_session,
                        'date': st.session_state.last_vid_date,
                        'animal_id': st.session_state.animal_id,
                        'counts': {'attempts': s_count + f_count, 'success': s_count, 'fail': f_count}
                    }
                    st.session_state.show_save_dialog = True
                    
                    # Reset trackers for the new session
                    st.session_state.video_outcomes = {}
                    st.session_state.animal_id = "" 
                
                st.session_state.frame_number = 0
                st.session_state.is_playing = False
                st.session_state.current_video = selected_video
                st.session_state.current_session = vid_session
                st.session_state.last_vid_date = vid_date
                
                if st.session_state.show_save_dialog:
                    st.rerun() 
        
        # ==========================================
        # DATA ENTRY COLUMN (MIDDLE)
        # ==========================================
        with col_data:
            st.subheader("📝 Session Data")
            
            st.session_state.animal_id = st.text_input(
                "Animal ID:", 
                value=st.session_state.animal_id,
                placeholder="e.g. Mouse_12"
            )
            st.markdown(f"**Current Session:** `{st.session_state.current_session}`")
            st.markdown("---")
            
            # Display current video's recorded status
            current_status = st.session_state.video_outcomes.get(selected_video, "Unclassified")
            
            # Color code the status for quick reading
            status_colors = {
                "Success": "🟢 **Success**",
                "Fail": "🔴 **Fail**",
                "Ignore": "⚪ **Ignored (Not an attempt)**",
                "Unclassified": "🟡 **Unclassified**"
            }
            st.markdown(f"Current Video Status: {status_colors.get(current_status)}")
            
            # --- UPDATED: Per-Video Logging Buttons ---
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            
            if btn_col1.button("✅ Success", use_container_width=True):
                st.session_state.video_outcomes[selected_video] = 'Success'
                st.rerun()
            if btn_col2.button("❌ Fail", use_container_width=True):
                st.session_state.video_outcomes[selected_video] = 'Fail'
                st.rerun()
            if btn_col3.button("🚫 Ignore", use_container_width=True, help="Mark this video as a non-attempt"):
                st.session_state.video_outcomes[selected_video] = 'Ignore'
                st.rerun()
                
            # --- UPDATED: Dynamic Calculation for Table ---
            succ = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Success')
            fail = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Fail')
            att = succ + fail # Attempts only count Success or Fail outcomes!
            
            rate = (succ / att * 100) if att > 0 else 0.0
            
            df = pd.DataFrame([{
                "Attempt": att,
                "Success": succ,
                "Fail": fail,
                "Success Rate": f"{rate:.1f}%"
            }])
            
            st.markdown("<br>**Session Summary Table:**", unsafe_allow_html=True)
            st.dataframe(df, hide_index=True, use_container_width=True)

        # ==========================================
        # VIDEO PLAYER COLUMN (LEFT)
        # ==========================================
        with col_video:
            if selected_video:
                st.subheader(f"📺 {selected_video}")
                video_path = os.path.join(folder_path, selected_video)
                
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