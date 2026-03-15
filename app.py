import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import cv2
import os
import time

# 1. Page Configuration
st.set_page_config(page_title="Reach Behavioral Analyzer", layout="wide")

st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 1rem;
        }
        
        div[data-testid="stDialog"] button[kind="secondary"] {
            background-color: #2e7d32 !important;
            color: white !important;
            border-color: #2e7d32 !important;
        }
        
        div[data-testid="stDialog"] button[kind="primary"] {
            background-color: #d32f2f !important;
            color: white !important;
            border-color: #d32f2f !important;
        }
        
        .active-vid {
            background-color: rgba(46, 125, 50, 0.2);
            padding: 8px;
            border-radius: 5px;
            border-left: 4px solid #2e7d32;
            margin-bottom: 5px;
        }
        
        .date-header {
            margin-top: 15px;
            margin-bottom: 5px;
            font-size: 1.1em;
            color: #444;
        }
        
        /* Force Streamlit to stop greying out images during playback */
        .stElementContainer, 
        div[data-testid="stImage"], 
        img {
            opacity: 1 !important;
            transition: none !important;
            filter: none !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- ULTRA-ROBUST JAVASCRIPT HOTKEYS ---
components.html(
    """
    <script>
    const parentWindow = window.parent;
    const parentDoc = parentWindow.document;

    function handleKeydown(e) {
        const activeTag = document.activeElement ? document.activeElement.tagName : "";
        const parentActiveTag = parentDoc.activeElement ? parentDoc.activeElement.tagName : "";
        
        // Ignore if you are typing an Animal ID in the text box
        if (activeTag === 'INPUT' || activeTag === 'TEXTAREA' || 
            parentActiveTag === 'INPUT' || parentActiveTag === 'TEXTAREA') {
            return;
        }

        let targetText = "";
        if (e.key === 'ArrowRight') targetText = 'Next ➡️';
        else if (e.key === 'ArrowLeft') targetText = '⬅️ Prev';
        else if (e.key === 'ArrowDown') targetText = '⬇️ Next Vid';
        else if (e.key === 'ArrowUp') targetText = '⬆️ Prev Vid';
        else if (e.key.toLowerCase() === 's') targetText = '✅ Success';
        else if (e.key.toLowerCase() === 'f') targetText = '❌ Fail';
        else if (e.key.toLowerCase() === 'i') targetText = '🚫 Ignore';
        else if (e.code === 'Space' || e.key === ' ') targetText = 'PLAY_PAUSE';

        if (targetText !== "") {
            // Kill default browser scrolling immediately
            e.preventDefault();
            e.stopPropagation();

            // Hunt down the button by its exact text
            const buttons = Array.from(parentDoc.querySelectorAll('button'));
            let btnToClick = null;

            if (targetText === 'PLAY_PAUSE') {
                btnToClick = buttons.find(b => b.innerText.includes('▶️ Play') || b.innerText.includes('⏸️ Pause'));
            } else {
                btnToClick = buttons.find(b => b.innerText.includes(targetText));
            }

            if (btnToClick) btnToClick.click();
        }
    }

    // CRITICAL FIX: Wipe out any old listeners from previous Streamlit redraws
    if (parentWindow._custom_hotkeys) {
        parentWindow.removeEventListener('keydown', parentWindow._custom_hotkeys, { capture: true });
    }
    
    // Attach the fresh listener to the absolute top level of the browser
    parentWindow._custom_hotkeys = handleKeydown;
    parentWindow.addEventListener('keydown', handleKeydown, { passive: false, capture: true });
    
    // Safety net: attach to the iframe itself just in case it steals focus
    window.addEventListener('keydown', handleKeydown, { passive: false, capture: true });
    </script>
    """,
    height=0,
    width=0,
)

st.title("🐁 Reach Behavioral Analyzer")

# ==========================================
# 2. State Management Initialization
# ==========================================
if 'frame_number' not in st.session_state: st.session_state.frame_number = 0
if 'is_playing' not in st.session_state: st.session_state.is_playing = False
if 'display_height' not in st.session_state: st.session_state.display_height = 400

if 'current_video' not in st.session_state: st.session_state.current_video = None
if 'current_session' not in st.session_state: st.session_state.current_session = None
if 'last_vid_date' not in st.session_state: st.session_state.last_vid_date = None
if 'video_outcomes' not in st.session_state: st.session_state.video_outcomes = {} 
if 'animal_id' not in st.session_state: st.session_state.animal_id = ""
if 'current_folder' not in st.session_state: st.session_state.current_folder = "."
if 'data_is_saved' not in st.session_state: st.session_state.data_is_saved = True

if 'video_paths_map' not in st.session_state: st.session_state.video_paths_map = {}
if 'folder_loaded' not in st.session_state: st.session_state.folder_loaded = ""
if 'video_files_list' not in st.session_state: st.session_state.video_files_list = []

if 'video_frames' not in st.session_state: st.session_state.video_frames = []
if 'loaded_video_name' not in st.session_state: st.session_state.loaded_video_name = None
if 'video_aspect_ratio' not in st.session_state: st.session_state.video_aspect_ratio = 1.0
if 'video_fps' not in st.session_state: st.session_state.video_fps = 150.0

# ==========================================
# 3. Core Functions & Callbacks
# ==========================================

def get_conflict_status(video_name, manual_outcome):
    if manual_outcome == "Ignore":
        return 1
    base_name = os.path.splitext(video_name)[0]
    auto_label = base_name.split('_')[-1].lower()
    manual_label = manual_outcome.lower()
    if manual_label in auto_label:
        return 0
    return 1

def close_session():
    st.session_state.video_outcomes = {}
    st.session_state.animal_id = ""
    st.session_state.data_is_saved = True 
    st.session_state.current_video = None
    st.session_state.current_session = None
    st.session_state.last_vid_date = None
    st.session_state.frame_number = 0
    st.session_state.is_playing = False
    st.session_state.video_frames = []
    st.session_state.loaded_video_name = None

def switch_to_video(new_vid):
    if not new_vid or not isinstance(new_vid, str): 
        return
        
    parts = new_vid.split('_')
    new_session = parts[2] if len(parts) >= 3 else "unknown"
    vid_date = parts[1] if len(parts) >= 3 else "000000"
    
    if st.session_state.current_session and new_session != st.session_state.current_session:
        st.session_state.video_outcomes = {}
        st.session_state.animal_id = ""
        st.session_state.data_is_saved = True 
        
    st.session_state.current_video = new_vid
    st.session_state.current_session = new_session
    st.session_state.last_vid_date = vid_date
    st.session_state.frame_number = 0
    st.session_state.is_playing = False

def prev_video_in_session():
    vids = st.session_state.video_files_list
    if not st.session_state.current_video or not vids: return
    try:
        curr_idx = vids.index(st.session_state.current_video)
        if curr_idx > 0:
            prev_vid = vids[curr_idx - 1]
            if prev_vid.split('_')[2] == st.session_state.current_session:
                switch_to_video(prev_vid)
    except ValueError:
        pass

def next_video_in_session():
    vids = st.session_state.video_files_list
    if not st.session_state.current_video or not vids: return
    try:
        curr_idx = vids.index(st.session_state.current_video)
        if curr_idx < len(vids) - 1:
            next_vid = vids[curr_idx + 1]
            if next_vid.split('_')[2] == st.session_state.current_session:
                switch_to_video(next_vid)
    except ValueError:
        pass

def process_uploaded_file(uploaded_file, vid_files):
    try:
        df_loaded = pd.read_csv(uploaded_file)
        if "Video" in df_loaded.columns and "Outcome" in df_loaded.columns:
            st.session_state.video_outcomes = dict(zip(df_loaded["Video"], df_loaded["Outcome"]))
            st.session_state.data_is_saved = True 
            
            file_name = uploaded_file.name
            if "_behaviorCounts.csv" in file_name:
                prefix = file_name.replace("_behaviorCounts.csv", "")
                # Splitting the prefix based on the new filename format
                parts = prefix.split("_")
                if len(parts) >= 3:
                    # Depending on how the string splits, we grab the animal ID
                    # YYMMDD_session_animalID
                    st.session_state.animal_id = parts[2]
            
            first_video_in_session = df_loaded["Video"].iloc[0]
            if first_video_in_session in vid_files:
                switch_to_video(first_video_in_session)
    except Exception as e:
        st.error(f"Error loading file: {e}")

def mark_as_saved():
    st.session_state.data_is_saved = True

@st.dialog("💾 Session Complete: Save Data")
def save_session_dialog(intended_vid=None, action="switch"):
    if action == "close":
        st.warning(f"You have unsaved changes. Please save the data for **{st.session_state.current_session}** before closing.")
    else:
        st.warning(f"You are attempting to switch sessions. Please save the data for **{st.session_state.current_session}** first.")
        
    date_str = st.session_state.last_vid_date
    yymmdd = date_str[2:] if len(date_str) == 8 else date_str 
    anim_id = st.session_state.animal_id.strip() if st.session_state.animal_id.strip() else "UnknownID"
    session_id = st.session_state.current_session if st.session_state.current_session else "unknownSession"
    
    # --- UPDATED: New CSV Filename Format ---
    filename = f"{yymmdd}_{session_id}_{anim_id}_behaviorCounts.csv"
    
    current_vid_abs_path = st.session_state.video_paths_map.get(st.session_state.current_video, st.session_state.current_folder)
    save_dir = os.path.dirname(current_vid_abs_path)
    save_path = os.path.join(save_dir, filename)
    
    succ = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Success')
    fail = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Fail')
    att = succ + fail
    rate = (succ / att * 100) if att > 0 else 0.0
    
    data_list = [{"Video": v, "Outcome": o, "Conflict": get_conflict_status(v, o)} for v, o in st.session_state.video_outcomes.items()]
    df_save = pd.DataFrame(data_list)
    df_save["Total_Attempts"] = att
    df_save["Total_Success"] = succ
    df_save["Total_Fail"] = fail
    df_save["Success_Rate_%"] = round(rate, 1)
    
    csv_data = df_save.to_csv(index=False)
    file_exists = os.path.exists(save_path)
    
    if file_exists:
        st.error(f"⚠️ **Warning:** `{filename}` already exists in the `{os.path.basename(save_dir)}` folder.")
        confirm_overwrite = st.checkbox("I confirm I want to overwrite the existing file.")
        disable_save = not confirm_overwrite
        btn_label = f"⚠️ Overwrite '{filename}' & " + ("Close" if action == "close" else "Switch")
    else:
        disable_save = False
        btn_label = f"💾 Save '{filename}' to Folder & " + ("Close" if action == "close" else "Switch")

    if st.button(btn_label, width="stretch", disabled=disable_save):
        try:
            with open(save_path, "w") as f:
                f.write(csv_data)
                
            if action == "close":
                close_session()
            else:
                switch_to_video(intended_vid)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to save file. Error: {e}")
    
    st.markdown("---")
    discard_label = "🗑️ Discard Data & Close" if action == "close" else "🗑️ Discard Data & Switch Anyway"
    if st.button(discard_label, type="primary", width="stretch"):
        if action == "close":
            close_session()
        else:
            if intended_vid: switch_to_video(intended_vid)
        st.rerun()

def handle_video_click(new_vid):
    parts = new_vid.split('_')
    new_session = parts[2] if len(parts) >= 3 else "unknown"
    
    if st.session_state.current_session and new_session != st.session_state.current_session:
        if not st.session_state.data_is_saved and len(st.session_state.video_outcomes) > 0:
            save_session_dialog(intended_vid=new_vid, action="switch")
        else:
            switch_to_video(new_vid)
    else:
        switch_to_video(new_vid)

def classify_and_advance(outcome, video_files):
    current_vid = st.session_state.current_video
    st.session_state.video_outcomes[current_vid] = outcome
    st.session_state.data_is_saved = False 
    
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

# Scrubbing Callbacks
def next_frame(total_frames):
    if st.session_state.frame_number < total_frames - 1: st.session_state.frame_number += 1
def prev_frame():
    if st.session_state.frame_number > 0: st.session_state.frame_number -= 1
def sync_jump(): st.session_state.frame_number = st.session_state.jump_input
def sync_slider(): st.session_state.frame_number = st.session_state.slider_frame
def toggle_play(): st.session_state.is_playing = not st.session_state.is_playing


# ==========================================
# VIDEO PLAYER FRAGMENT (PURE OPENCV)
# ==========================================
@st.fragment
def video_player_fragment():
    active_vid = st.session_state.current_video
    if not active_vid:
        return

    video_path = st.session_state.video_paths_map[active_vid]

    # Pre-load entire video into RAM with aggressive compression
    if active_vid != st.session_state.loaded_video_name:
        with st.spinner("Loading video into memory for fast playback..."):
            cap = cv2.VideoCapture(video_path)
            frames = []
            if cap.isOpened():
                st.session_state.video_fps = 150.0 
                
                while True:
                    ret, frame = cap.read()
                    if not ret: break
                    
                    h, w, _ = frame.shape
                    
                    target_width = 700 
                    scale = target_width / float(w)
                    target_height = int(h * scale)
                    
                    resized_frame = cv2.resize(frame, (target_width, target_height))
                    
                    if len(frames) == 0:
                        st.session_state.video_aspect_ratio = float(w) / float(h)
                    
                    success, buffer = cv2.imencode('.jpg', resized_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                    if success:
                        frames.append(buffer.tobytes())
                        
                cap.release()
                st.session_state.video_frames = frames
                st.session_state.loaded_video_name = active_vid
                st.session_state.frame_number = 0
            else:
                st.error("Failed to open video file.")
                return

    frames = st.session_state.video_frames
    total_frames = len(frames)

    if total_frames > 0:
        st.write(f"**Frames:** {total_frames} | **Camera FPS:** {st.session_state.video_fps:.0f} | **RAM Cache:** Active")

        col_height, col_speed = st.columns(2)
        with col_height:
            st.slider("📏 Display Height", min_value=100, max_value=1080, step=50, key="display_height")
        with col_speed:
            target_playback_fps = st.slider("⏱️ Playback Speed (App FPS)", min_value=10, max_value=60, value=25, step=5, 
                                            help="Your camera is 150 FPS. Playing at 25 FPS = 6x slow motion.")
        
        if st.session_state.frame_number >= total_frames:
            st.session_state.frame_number = total_frames - 1

        calc_width = int(st.session_state.display_height * st.session_state.video_aspect_ratio)
        st.image(frames[st.session_state.frame_number], width=calc_width)
        st.markdown("---")

        st.session_state.slider_frame = st.session_state.frame_number
        st.session_state.jump_input = st.session_state.frame_number

        col_play, col_prev, col_input, col_next = st.columns([1, 1, 3, 1])

        with col_play:
            play_label = "⏸️ Pause" if st.session_state.is_playing else "▶️ Play"
            st.button(play_label, width="stretch", on_click=toggle_play, help="Hotkey: Spacebar")

        with col_prev:
            st.button("⬅️ Prev", width="stretch", on_click=prev_frame, help="Hotkey: Left Arrow")
                
        with col_input:
            st.slider("Scrub Frames", min_value=0, max_value=max(0, total_frames - 1), key="slider_frame", on_change=sync_slider, label_visibility="collapsed")
                
        with col_next:
            st.button("Next ➡️", width="stretch", on_click=next_frame, args=(total_frames,), help="Hotkey: Right Arrow")

        st.number_input("Jump to exact frame:", min_value=0, max_value=max(0, total_frames - 1), step=1, key="jump_input", on_change=sync_jump)

        if st.session_state.is_playing:
            if st.session_state.frame_number < total_frames - 1:
                sleep_delay = 1.0 / target_playback_fps
                time.sleep(sleep_delay) 
                st.session_state.frame_number += 1
                st.rerun()       
            else:
                st.session_state.is_playing = False 
                st.rerun()
    else:
        st.error("Could not load frames into memory.")

# ==========================================
# 4. Main App Layout
# ==========================================
folder_path = st.text_input("📁 Enter the root directory path (e.g., .../learning/):", value=".")
st.session_state.current_folder = folder_path 

if os.path.exists(folder_path) and os.path.isdir(folder_path):
    supported_exts = ('.mp4', '.mkv', '.mov', '.avi')
    video_files = []
    
    st.session_state.video_paths_map.clear()
    
    for root, dirs, files in os.walk(folder_path):
        
        # --- FIX: Dynamically ignore both subdirectories ---
        if 'foregrounds' in dirs:
            dirs.remove('foregrounds')
        if 'rawfragments' in dirs:
            dirs.remove('rawfragments')
            
        # Ignore stray videos sitting in the main root directory
        if os.path.abspath(root) == os.path.abspath(folder_path):
            continue
            
        for f in files:
            # Added 'v_' check so we never grab background.mp4 or other files
            if f.lower().endswith(supported_exts) and f.startswith('v_'):
                video_files.append(f)
                st.session_state.video_paths_map[f] = os.path.join(root, f)

    video_files = sorted(video_files)
    st.session_state.video_files_list = video_files 

    if video_files:
        if st.session_state.folder_loaded != folder_path:
            st.session_state.folder_loaded = folder_path
            switch_to_video(video_files[0])
            
        hierarchy = {}
        for v in video_files:
            parts = v.split('_')
            date_folder = parts[1] if len(parts) >= 3 else "unknown_date"
            sess = parts[2] if len(parts) >= 3 else "unknown_session"
            
            if date_folder not in hierarchy:
                hierarchy[date_folder] = {}
            if sess not in hierarchy[date_folder]:
                hierarchy[date_folder][sess] = []
            hierarchy[date_folder][sess].append(v)

        col_video, col_data, col_playlist = st.columns([4, 2.5, 2])
        
        # ==========================================
        # PLAYLIST COLUMN (RIGHT)
        # ==========================================
        with col_playlist:
            st.subheader("📋 Playlist")
            
            for date_str, sessions in sorted(hierarchy.items()):
                is_active_date = (date_str == st.session_state.last_vid_date)
                
                with st.expander(f"📅 **{date_str}**", expanded=is_active_date):
                    for sess, vids in sorted(sessions.items()):
                        is_current_session = (sess == st.session_state.current_session)
                        
                        with st.expander(f"📁 {sess} ({len(vids)} files)", expanded=is_current_session):
                            for vid in vids:
                                if vid == st.session_state.current_video:
                                    st.markdown(f"<div class='active-vid'>▶️ <b>{vid}</b></div>", unsafe_allow_html=True)
                                else:
                                    st.button(f"📄 {vid}", key=f"btn_{vid}", width="stretch", on_click=handle_video_click, args=(vid,))
        
        # ==========================================
        # DATA ENTRY COLUMN (MIDDLE)
        # ==========================================
        with col_data:
            st.subheader("📝 Session Data")
            
            uploaded_file = st.file_uploader("📥 Upload CSV to Resume Data", type=['csv'])
            if uploaded_file is not None:
                st.button("🔄 Load Uploaded Data", width="stretch", on_click=process_uploaded_file, args=(uploaded_file, video_files))
            
            st.markdown("---")
            
            if not st.session_state.current_session:
                st.info("Select a video from the playlist to start a new session 👉.")
            
            else:
                has_data_logged = len(st.session_state.video_outcomes) > 0
                
                col_id, col_close = st.columns([3, 1])
                with col_id:
                    st.session_state.animal_id = st.text_input(
                        "Animal ID:", 
                        value=st.session_state.animal_id, 
                        placeholder="e.g. Mouse_12",
                        disabled=has_data_logged,
                        label_visibility="collapsed"
                    )
                with col_close:
                    if st.button("❌ Close", width="stretch", help="Close this session to start fresh."):
                        if not st.session_state.data_is_saved and has_data_logged:
                            save_session_dialog(action="close")
                        else:
                            close_session()
                            st.rerun()

                st.markdown(f"**Current Session:** `{st.session_state.current_session}`")
                
                current_session_vids = hierarchy.get(st.session_state.last_vid_date, {}).get(st.session_state.current_session, [])
                total_session_vids = len(current_session_vids)
                categorized_count = len(st.session_state.video_outcomes)
                
                st.markdown(f"**Progress:** {categorized_count} / {total_session_vids} categorized")
                st.progress(categorized_count / total_session_vids if total_session_vids > 0 else 0)
                
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
                btn_col1.button("✅ Success", width="stretch", on_click=classify_and_advance, args=('Success', video_files), help="Hotkey: 'S'")
                btn_col2.button("❌ Fail", width="stretch", on_click=classify_and_advance, args=('Fail', video_files), help="Hotkey: 'F'")
                btn_col3.button("🚫 Ignore", width="stretch", on_click=classify_and_advance, args=('Ignore', video_files), help="Hotkey: 'I'")
                
                succ = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Success')
                fail = sum(1 for v in st.session_state.video_outcomes.values() if v == 'Fail')
                att = succ + fail 
                rate = (succ / att * 100) if att > 0 else 0.0
                
                df_summary = pd.DataFrame([{"Attempt": att, "Success": succ, "Fail": fail, "Success Rate": f"{rate:.1f}%"}])
                st.markdown("<br>**Session Summary:**", unsafe_allow_html=True)
                st.dataframe(df_summary, hide_index=True, width="stretch")

                st.markdown("**Editable Raw Data:**", help="Double-click any cell in the Outcome column to manually fix errors.")
                if st.session_state.video_outcomes:
                    data_list = [{"Video": v, "Outcome": o, "Conflict": get_conflict_status(v, o)} for v, o in st.session_state.video_outcomes.items()]
                    df_raw = pd.DataFrame(data_list)
                    
                    edited_df = st.data_editor(
                        df_raw, 
                        width="stretch", 
                        hide_index=True,
                        disabled=["Video", "Conflict"] 
                    )
                    
                    new_outcomes = dict(zip(edited_df["Video"], edited_df["Outcome"]))
                    if new_outcomes != st.session_state.video_outcomes:
                        st.session_state.video_outcomes = new_outcomes
                        st.session_state.data_is_saved = False
                        st.rerun()

                st.markdown("---")
                st.markdown("**Manual Export:**")
                
                date_str = st.session_state.last_vid_date if st.session_state.last_vid_date else "000000"
                yymmdd = date_str[2:] if len(date_str) == 8 else date_str 
                anim_id = st.session_state.animal_id.strip() if st.session_state.animal_id.strip() else "UnknownID"
                session_id = st.session_state.current_session if st.session_state.current_session else "unknownSession"
                
                # --- UPDATED: New CSV Filename Format ---
                manual_filename = f"{yymmdd}_{session_id}_{anim_id}_behaviorCounts.csv"
                
                if st.session_state.video_outcomes:
                    df_manual_save = pd.DataFrame(data_list) 
                else:
                    df_manual_save = pd.DataFrame(columns=["Video", "Outcome", "Conflict"])
                    
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
                    width="stretch",
                    on_click=mark_as_saved 
                )

        # ==========================================
        # VIDEO PLAYER COLUMN (LEFT)
        # ==========================================
        with col_video:
            if not st.session_state.current_video:
                st.info("No video selected. Please select a video from the playlist to begin analysis.")
            else:
                active_vid = st.session_state.current_video
                
                col_title, col_up, col_down = st.columns([6, 1.5, 1.5])
                with col_title:
                    st.subheader(f"📺 {active_vid}")
                with col_up:
                    st.button("⬆️ Prev Vid", width="stretch", on_click=prev_video_in_session, help="Hotkey: Up Arrow")
                with col_down:
                    st.button("⬇️ Next Vid", width="stretch", on_click=next_video_in_session, help="Hotkey: Down Arrow")
                    
                video_player_fragment()

    else:
        st.warning("No supported video files found in this directory or subdirectories.")
else:
    st.error("Please enter a valid folder path.")