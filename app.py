import streamlit as st
import pandas as pd
import cv2
import os
import time
import concurrent.futures
import re
import warnings
import logging
import streamlit.components.v1 as components

# --- AGGRESSIVELY SILENCE STREAMLIT DEPRECATION SPAM IN TERMINAL ---
warnings.filterwarnings("ignore", message=".*st.components.v1.html.*")
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Target specific Streamlit loggers that bypass standard warnings
logging.getLogger("streamlit.deprecation").setLevel(logging.ERROR)
logging.getLogger("streamlit.elements.iframe").setLevel(logging.ERROR)
for log_name in logging.root.manager.loggerDict:
    if "streamlit" in log_name.lower():
        logging.getLogger(log_name).setLevel(logging.ERROR)

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

# --- DUAL-ATTACHMENT JAVASCRIPT ENGINE W/ THROTTLING & BLUR ---
js_code = """
<script>
const parentWindow = window.parent;
const parentDoc = parentWindow.document;

// Clean up old listeners to prevent double-firing on reruns
if (parentWindow._custom_hotkeys) {
    parentWindow.removeEventListener('keydown', parentWindow._custom_hotkeys, { capture: true });
    window.removeEventListener('keydown', parentWindow._custom_hotkeys, { capture: true });
}

let lastScrubTime = 0;

function handleKeydown(e) {
    const activeEl = document.activeElement;
    const parentActiveEl = parentDoc.activeElement;
    
    // Safely allow the user to type inside text boxes
    const isTextInput = (el) => {
        if (!el) return false;
        const tag = el.tagName ? el.tagName.toUpperCase() : '';
        const type = el.type ? el.type.toLowerCase() : '';
        if (tag === 'TEXTAREA') return true;
        if (tag === 'INPUT' && ['text', 'number', 'password', 'search'].includes(type)) return true;
        return false;
    };

    if (isTextInput(activeEl) || isTextInput(parentActiveEl)) {
        return;
    }

    // Force blur on the Streamlit slider if arrow keys are pressed so it doesn't swallow the event
    if ((activeEl && activeEl.type === 'range') || (parentActiveEl && parentActiveEl.type === 'range')) {
        if (['ArrowRight', 'ArrowLeft', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
            if (activeEl && activeEl.blur) activeEl.blur();
            if (parentActiveEl && parentActiveEl.blur) parentActiveEl.blur();
        }
    }

    let targetText = "";
    
    // Arrow Logic with Throttling for "Holding Down" functionality
    if (e.key === 'ArrowRight') {
        targetText = 'Next ➡️';
        if (e.repeat) {
            // Limits continuous scrolling to ~10 FPS to prevent Streamlit WebSocket crashes
            if (Date.now() - lastScrubTime < 100) { e.preventDefault(); return; }
            lastScrubTime = Date.now();
        }
    }
    else if (e.key === 'ArrowLeft') {
        targetText = '⬅️ Prev';
        if (e.repeat) {
            if (Date.now() - lastScrubTime < 100) { e.preventDefault(); return; }
            lastScrubTime = Date.now();
        }
    }
    else if (e.key === 'ArrowDown') { targetText = '⬇️ Next Vid'; if (e.repeat) { e.preventDefault(); return; } }
    else if (e.key === 'ArrowUp') { targetText = '⬆️ Prev Vid'; if (e.repeat) { e.preventDefault(); return; } }
    else if (e.key.toLowerCase() === 's') { targetText = '✅ Success'; if (e.repeat) { e.preventDefault(); return; } }
    else if (e.key.toLowerCase() === 'f') { targetText = '❌ Fail'; if (e.repeat) { e.preventDefault(); return; } }
    else if (e.key.toLowerCase() === 'i') { targetText = '🚫 Ignore'; if (e.repeat) { e.preventDefault(); return; } }
    else if (e.code === 'Space' || e.key === ' ') {
        targetText = 'PLAY_PAUSE';
        if (e.repeat) { e.preventDefault(); return; } 
    }

    if (targetText !== "") {
        e.preventDefault();
        e.stopPropagation();

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

// Bind to both windows to guarantee capture regardless of iframe focus state
parentWindow._custom_hotkeys = handleKeydown;
parentWindow.addEventListener('keydown', handleKeydown, { passive: false, capture: true });
window.addEventListener('keydown', handleKeydown, { passive: false, capture: true });
</script>
"""

# Inject invisibly
components.html(js_code, height=1, width=1)


# ==========================================
# 2. State Management Initialization
# ==========================================
if 'frame_number' not in st.session_state: st.session_state.frame_number = 0
if 'is_playing' not in st.session_state: st.session_state.is_playing = False

# Explicitly setting Default Values for sliders to prevent 100px reset bug
if 'display_height' not in st.session_state: st.session_state.display_height = 350
if 'target_fps' not in st.session_state: st.session_state.target_fps = 30

if 'current_video' not in st.session_state: st.session_state.current_video = None
if 'current_session' not in st.session_state: st.session_state.current_session = None
if 'last_vid_date' not in st.session_state: st.session_state.last_vid_date = None

if 'session_events' not in st.session_state: st.session_state.session_events = [] 

if 'ledger_key' not in st.session_state: st.session_state.ledger_key = 0

if 'animal_id' not in st.session_state: st.session_state.animal_id = ""
if 'current_folder' not in st.session_state: st.session_state.current_folder = "."
if 'data_is_saved' not in st.session_state: st.session_state.data_is_saved = True

if 'video_paths_map' not in st.session_state: st.session_state.video_paths_map = {}
if 'folder_loaded' not in st.session_state: st.session_state.folder_loaded = ""
if 'video_files_list' not in st.session_state: st.session_state.video_files_list = []

if 'loaded_video_name' not in st.session_state: st.session_state.loaded_video_name = None
if 'video_aspect_ratio' not in st.session_state: st.session_state.video_aspect_ratio = 1.0
if 'video_fps' not in st.session_state: st.session_state.video_fps = 150.0

if 'total_frames' not in st.session_state: st.session_state.total_frames = 0
if 'frame_cache' not in st.session_state: st.session_state.frame_cache = {}
if 'bg_executor' not in st.session_state: st.session_state.bg_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
if 'prefetch_future' not in st.session_state: st.session_state.prefetch_future = None

# ==========================================
# 3. Core Functions & Callbacks
# ==========================================

def process_single_frame(args):
    frame_idx, frame, target_width = args
    h, w, _ = frame.shape
    scale = target_width / float(w)
    target_height = int(h * scale)
    
    resized_frame = cv2.resize(frame, (target_width, target_height))
    success, buffer = cv2.imencode('.jpg', resized_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    
    if success: return frame_idx, buffer.tobytes()
    return frame_idx, None

def fetch_frames_task(video_path, start_frame, num_frames, target_width=700):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    raw_frames = []
    for i in range(num_frames):
        ret, frame = cap.read()
        if not ret: break
        raw_frames.append((start_frame + i, frame, target_width))
        
    cap.release()
    
    new_frames = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        for frame_idx, buffer_bytes in executor.map(process_single_frame, raw_frames):
            if buffer_bytes: new_frames[frame_idx] = buffer_bytes
                
    return new_frames

def get_conflict_status(video_name, manual_outcome):
    if manual_outcome == "Ignore": return 1
    base_name = os.path.splitext(video_name)[0]
    auto_label = base_name.split('_')[-1].lower()
    manual_label = manual_outcome.lower()
    if manual_label in auto_label: return 0
    return 1

def close_session():
    st.session_state.session_events = []
    st.session_state.animal_id = ""
    st.session_state.data_is_saved = True 
    st.session_state.current_video = None
    st.session_state.current_session = None
    st.session_state.last_vid_date = None
    st.session_state.frame_number = 0
    st.session_state.is_playing = False
    st.session_state.frame_cache = {}
    st.session_state.loaded_video_name = None

def switch_to_video(new_vid):
    if not new_vid or not isinstance(new_vid, str): return
    
    date_match = re.search(r'(20\d{6})', new_vid)
    vid_date = date_match.group(1) if date_match else "000000"
    
    sess_match = re.search(r'(session\d{3})', new_vid)
    new_session = sess_match.group(1) if sess_match else "unknown"
    
    if st.session_state.current_session and new_session != st.session_state.current_session:
        st.session_state.session_events = []
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
            sess_match = re.search(r'(session\d{3})', prev_vid)
            prev_session = sess_match.group(1) if sess_match else "unknown"
            if prev_session == st.session_state.current_session:
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
            sess_match = re.search(r'(session\d{3})', next_vid)
            next_session = sess_match.group(1) if sess_match else "unknown"
            if next_session == st.session_state.current_session:
                switch_to_video(next_vid)
    except ValueError:
        pass

def process_uploaded_file(uploaded_file, vid_files):
    try:
        df_loaded = pd.read_csv(uploaded_file)
        if "Video" in df_loaded.columns and "Outcome" in df_loaded.columns:
            events = []
            for _, row in df_loaded.iterrows():
                frame_val = row.get("Frame", 0)
                try:
                    frame_int = int(float(frame_val)) if pd.notna(frame_val) else 0
                except (ValueError, TypeError):
                    frame_int = 0
                    
                events.append({
                    "Video": row["Video"],
                    "Outcome": row["Outcome"],
                    "Frame": frame_int,
                    "Conflict": get_conflict_status(row["Video"], row["Outcome"])
                })
            
            st.session_state.session_events = events
            st.session_state.data_is_saved = True 
            
            file_name = uploaded_file.name
            if "_behaviorCounts.csv" in file_name:
                prefix = file_name.replace("_behaviorCounts.csv", "")
                parts = prefix.split("_")
                if len(parts) >= 3: st.session_state.animal_id = parts[2]
            
            first_video_in_session = df_loaded["Video"].iloc[0]
            if first_video_in_session in vid_files: switch_to_video(first_video_in_session)
    except Exception as e:
        st.error(f"Error loading file: {e}")

def mark_as_saved(): st.session_state.data_is_saved = True

@st.dialog("💾 Session Complete: Save Data")
def save_session_dialog(intended_vid=None, action="switch"):
    if action == "close":
        st.warning(f"You have unsaved changes. Please save the data for **{st.session_state.current_session}** before closing.")
    else:
        st.warning(f"You are attempting to switch sessions. Please save the data for **{st.session_state.current_session}** first.")
        
    anim_id = st.session_state.animal_id.strip()
    
    if not anim_id:
        st.error("🚨 Missing Animal ID! You must provide an ID to enable saving.")
        
        def update_dialog_id():
            st.session_state.animal_id = st.session_state.dialog_anim_id
            
        st.text_input("Enter Animal ID here:", key="dialog_anim_id", on_change=update_dialog_id)
        
        st.markdown("---")
        discard_label = "🗑️ Discard Data & Close" if action == "close" else "🗑️ Discard Data & Switch Anyway"
        if st.button(discard_label, type="primary", width="stretch"):
            if action == "close": close_session()
            else:
                if intended_vid: switch_to_video(intended_vid)
            st.rerun()
            
        return 

    date_str = st.session_state.last_vid_date
    yymmdd = date_str[2:] if len(date_str) == 8 else date_str 
    session_id = st.session_state.current_session if st.session_state.current_session else "unknownSession"
    
    filename = f"{yymmdd}_{session_id}_{anim_id}_behaviorCounts.csv"
    
    current_vid_abs_path = st.session_state.video_paths_map.get(st.session_state.current_video, st.session_state.current_folder)
    save_dir = os.path.dirname(current_vid_abs_path)
    save_path = os.path.join(save_dir, filename)
    
    succ = sum(1 for e in st.session_state.session_events if e['Outcome'] == 'Success')
    fail = sum(1 for e in st.session_state.session_events if e['Outcome'] == 'Fail')
    att = succ + fail
    rate = (succ / att * 100) if att > 0 else 0.0
    
    if st.session_state.session_events:
        df_save = pd.DataFrame(st.session_state.session_events)
    else:
        df_save = pd.DataFrame(columns=["Video", "Outcome", "Frame", "Conflict"])
        
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
            with open(save_path, "w") as f: f.write(csv_data)
            if action == "close": close_session()
            else: switch_to_video(intended_vid)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to save file. Error: {e}")
    
    st.markdown("---")
    discard_label = "🗑️ Discard Data & Close" if action == "close" else "🗑️ Discard Data & Switch Anyway"
    if st.button(discard_label, type="primary", width="stretch"):
        if action == "close": close_session()
        else:
            if intended_vid: switch_to_video(intended_vid)
        st.rerun()

def handle_video_click(new_vid):
    sess_match = re.search(r'(session\d{3})', new_vid)
    new_session = sess_match.group(1) if sess_match else "unknown"
    
    if st.session_state.current_session and new_session != st.session_state.current_session:
        if not st.session_state.data_is_saved and len(st.session_state.session_events) > 0:
            save_session_dialog(intended_vid=new_vid, action="switch")
        else:
            switch_to_video(new_vid)
    else:
        switch_to_video(new_vid)

def log_outcome(outcome):
    current_vid = st.session_state.current_video
    current_frame = st.session_state.frame_number
    
    st.session_state.session_events.append({
        "Video": current_vid,
        "Outcome": outcome,
        "Frame": current_frame,
        "Conflict": get_conflict_status(current_vid, outcome)
    })
    st.session_state.data_is_saved = False 

def reset_play_timer():
    if 'play_start_time' in st.session_state: del st.session_state.play_start_time

def next_frame(total_frames):
    if st.session_state.frame_number < total_frames - 1: st.session_state.frame_number += 1
    reset_play_timer()
def prev_frame():
    if st.session_state.frame_number > 0: st.session_state.frame_number -= 1
    reset_play_timer()
def sync_jump(): 
    st.session_state.frame_number = st.session_state.jump_input
    reset_play_timer()
    
def sync_slider(): 
    st.session_state.frame_number = st.session_state.slider_frame
    reset_play_timer()

def update_height():
    st.session_state.display_height = st.session_state.ui_height_slider

def update_fps():
    st.session_state.target_fps = st.session_state.ui_fps_slider

def toggle_play(): 
    st.session_state.is_playing = not st.session_state.is_playing
    reset_play_timer()

# ==========================================
# VIDEO PLAYER FRAGMENT (SMART CHUNKING)
# ==========================================
@st.fragment
def video_player_fragment():
    active_vid = st.session_state.current_video
    if not active_vid: return

    video_path = st.session_state.video_paths_map[active_vid]

    if active_vid != st.session_state.loaded_video_name:
        with st.spinner("Initializing high-speed video buffer..."):
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                st.session_state.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                st.session_state.video_fps = fps if fps > 0 else 150.0 
                
                ret, frame = cap.read()
                if ret:
                    h, w, _ = frame.shape
                    st.session_state.video_aspect_ratio = float(w) / float(h)
                cap.release()

                st.session_state.loaded_video_name = active_vid
                st.session_state.frame_number = 0
                st.session_state.frame_cache = {}
                
                if 'bg_executor' in st.session_state: st.session_state.bg_executor.shutdown(wait=False)
                st.session_state.bg_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                st.session_state.prefetch_future = None
            else:
                st.error("Failed to open video file.")
                return

    total_frames = st.session_state.total_frames
    curr_frame = st.session_state.frame_number
    
    CHUNK_SIZE = 600
    PREFETCH_MARGIN = 250

    if curr_frame not in st.session_state.frame_cache:
        with st.spinner(f"Fast-buffering frames {curr_frame} to {min(curr_frame + CHUNK_SIZE, total_frames)}..."):
            start_f = max(0, curr_frame - 50) 
            st.session_state.frame_cache = fetch_frames_task(video_path, start_f, CHUNK_SIZE)
            st.session_state.prefetch_future = None

    if st.session_state.frame_cache:
        max_cached = max(st.session_state.frame_cache.keys())
        
        if (max_cached - curr_frame < PREFETCH_MARGIN) and max_cached < total_frames - 1:
            if st.session_state.prefetch_future is None or st.session_state.prefetch_future.done():
                
                if st.session_state.prefetch_future and st.session_state.prefetch_future.done():
                    try:
                        new_data = st.session_state.prefetch_future.result()
                        st.session_state.frame_cache.update(new_data)
                        
                        keys_to_del = [k for k in st.session_state.frame_cache.keys() if k < curr_frame - 500]
                        for k in keys_to_del: del st.session_state.frame_cache[k]
                    except Exception as e:
                        st.error(f"Prefetch error: {e}")
                        
                next_start = max(st.session_state.frame_cache.keys()) + 1
                if next_start < total_frames:
                    st.session_state.prefetch_future = st.session_state.bg_executor.submit(
                        fetch_frames_task, video_path, next_start, CHUNK_SIZE
                    )

    if total_frames > 0 and curr_frame in st.session_state.frame_cache:
        st.write(f"**Frames:** {total_frames} | **Camera FPS:** {st.session_state.video_fps:.0f} | **RAM Cache:** Parallel Chunking ({len(st.session_state.frame_cache)} frames active)")

        col_height, col_speed = st.columns(2)
        with col_height:
            st.slider("📏 Display Height", min_value=100, max_value=1080, 
                      value=st.session_state.display_height, step=50, 
                      key="ui_height_slider", on_change=update_height)
        with col_speed:
            target_playback_fps = st.slider("⏱️ Target Playback Speed (App FPS)", min_value=1, max_value=150, 
                                            value=st.session_state.target_fps, step=1, 
                                            key="ui_fps_slider", on_change=update_fps)
        
        if curr_frame >= total_frames:
            st.session_state.frame_number = total_frames - 1

        calc_width = int(st.session_state.display_height * st.session_state.video_aspect_ratio)
        st.image(st.session_state.frame_cache[curr_frame], width=calc_width)
        st.markdown("---")

        # --- EXPLICITLY BIND WIDGET STATES TO THE CURRENT FRAME ---
        st.session_state.slider_frame = curr_frame
        st.session_state.jump_input = curr_frame

        col_play, col_prev, col_input, col_next = st.columns([1, 1, 3, 1])

        with col_play:
            play_label = "⏸️ Pause" if st.session_state.is_playing else "▶️ Play"
            st.button(play_label, width="stretch", on_click=toggle_play, help="Hotkey: Spacebar")

        with col_prev:
            st.button("⬅️ Prev", width="stretch", on_click=prev_frame, help="Hotkey: Left Arrow")
                
        with col_input:
            st.slider("Scrub Frames", min_value=0, max_value=max(0, total_frames - 1), 
                      value=curr_frame, key="slider_frame", on_change=sync_slider, label_visibility="collapsed")
                
        with col_next:
            st.button("Next ➡️", width="stretch", on_click=next_frame, args=(total_frames,), help="Hotkey: Right Arrow")

        st.number_input("Jump to exact frame:", min_value=0, max_value=max(0, total_frames - 1), step=1, key="jump_input", on_change=sync_jump)

        if st.session_state.is_playing:
            if 'play_start_time' not in st.session_state:
                st.session_state.play_start_time = time.time()
                st.session_state.play_start_frame = curr_frame

            elapsed_time = time.time() - st.session_state.play_start_time
            expected_frame = int(st.session_state.play_start_frame + (elapsed_time * target_playback_fps))

            if expected_frame >= total_frames - 1:
                st.session_state.frame_number = total_frames - 1
                st.session_state.is_playing = False
                reset_play_timer()
                st.rerun()
            elif expected_frame > curr_frame:
                st.session_state.frame_number = expected_frame
                time.sleep(0.005) 
                st.rerun()
            else:
                time.sleep(0.005)
                st.rerun()
        else:
            reset_play_timer()

    else:
        if curr_frame not in st.session_state.frame_cache:
            st.error(f"Waiting for buffer at frame {curr_frame}...")

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
        if 'foregrounds' in dirs: dirs.remove('foregrounds')
        if 'rawfragments' in dirs: dirs.remove('rawfragments')
            
        if os.path.abspath(root) == os.path.abspath(folder_path): continue
            
        for f in files:
            if f.lower().endswith(supported_exts) and not f.startswith('.'):
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
            date_match = re.search(r'(20\d{6})', v) 
            date_folder = date_match.group(1) if date_match else "unknown_date"
            
            sess_match = re.search(r'(session\d{3})', v)
            sess = sess_match.group(1) if sess_match else "unknown_session"
            
            if date_folder not in hierarchy: hierarchy[date_folder] = {}
            if sess not in hierarchy[date_folder]: hierarchy[date_folder][sess] = []
            hierarchy[date_folder][sess].append(v)

        col_video, col_side = st.columns([4, 4.5])
        
        # ==========================================
        # RIGHT SIDE PANEL (Data, Playlist, Ledger)
        # ==========================================
        with col_side:
            col_data, col_playlist = st.columns([2.5, 2])
            
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
            
            with col_data:
                st.subheader("📝 Session Data")
                
                uploaded_file = st.file_uploader("📥 Upload CSV to Resume Data", type=['csv'])
                if uploaded_file is not None:
                    st.button("🔄 Load Uploaded Data", width="stretch", on_click=process_uploaded_file, args=(uploaded_file, video_files))
                
                st.markdown("---")
                
                if not st.session_state.current_session:
                    st.info("Select a video from the playlist to start a new session 👉.")
                
                else:
                    has_data_logged = len(st.session_state.session_events) > 0
                    
                    col_id, col_close = st.columns([3, 1])
                    with col_id:
                        st.session_state.animal_id = st.text_input(
                            "Animal ID:", 
                            value=st.session_state.animal_id, 
                            placeholder="e.g. Mouse_12",
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
                    
                    vids_with_events = len(set([e["Video"] for e in st.session_state.session_events]))
                    
                    st.markdown(f"**Progress:** {vids_with_events} / {total_session_vids} videos actively tracked")
                    st.progress(vids_with_events / total_session_vids if total_session_vids > 0 else 0)
                    
                    st.markdown("---")
                    
                    current_vid = st.session_state.current_video
                    current_events = [e for e in st.session_state.session_events if e["Video"] == current_vid]
                    
                    st.markdown(f"**Events Logged in this Video:** `{len(current_events)}`")
                    if current_events:
                        for ev in current_events[-3:]:
                            status_colors = {"Success": "🟢", "Fail": "🔴", "Ignore": "⚪"}
                            icon = status_colors.get(ev["Outcome"], "🟡")
                            st.caption(f"↳ {icon} {ev['Outcome']} logged at Frame {ev['Frame']}")
                    
                    btn_col1, btn_col2, btn_col3 = st.columns(3)
                    btn_col1.button("✅ Success", width="stretch", on_click=log_outcome, args=('Success',), help="Hotkey: 'S'")
                    btn_col2.button("❌ Fail", width="stretch", on_click=log_outcome, args=('Fail',), help="Hotkey: 'F'")
                    btn_col3.button("🚫 Ignore", width="stretch", on_click=log_outcome, args=('Ignore',), help="Hotkey: 'I'")
                    
                    succ = sum(1 for e in st.session_state.session_events if e['Outcome'] == 'Success')
                    fail = sum(1 for e in st.session_state.session_events if e['Outcome'] == 'Fail')
                    att = succ + fail 
                    rate = (succ / att * 100) if att > 0 else 0.0
                    
                    df_summary = pd.DataFrame([{"Total Attempts": att, "Successes": succ, "Failures": fail, "Success Rate": f"{rate:.1f}%"}])
                    st.markdown("<br>**Session Summary:**", unsafe_allow_html=True)
                    st.dataframe(df_summary, hide_index=True, width="stretch")

            # ==========================================
            # FULL WIDTH LEDGER
            # ==========================================
            if st.session_state.current_session:
                st.markdown("---")
                st.markdown("**Editable Event Ledger:**", help="Check the '🔍 Go To' box to instantly jump to that frame. Click the trash can to delete.")
                if st.session_state.session_events:
                    
                    ui_events = []
                    for e in st.session_state.session_events:
                        ui_events.append({
                            "🔍 Go To": False, 
                            "Video": e["Video"],
                            "Outcome": e["Outcome"],
                            "Frame": e["Frame"],
                            "Conflict": e["Conflict"]
                        })
                        
                    df_raw = pd.DataFrame(ui_events)
                    
                    edited_df = st.data_editor(
                        df_raw, 
                        key=f"editor_{st.session_state.ledger_key}", 
                        width="stretch", 
                        hide_index=True,
                        num_rows="dynamic",
                        disabled=["Conflict"],
                        column_config={
                            "🔍 Go To": st.column_config.CheckboxColumn(
                                "🔍 Go To",
                                help="Check box to instantly jump the video to this specific frame.",
                                default=False,
                            )
                        }
                    )
                    
                    seek_triggered = False
                    target_frame = 0
                    target_vid = None
                    
                    new_events = []
                    for _, row in edited_df.iterrows():
                        if row.get("🔍 Go To", False) == True:
                            seek_triggered = True
                            
                        raw_frame = row.get("Frame", 0)
                        try:
                            clean_frame = int(float(raw_frame)) if pd.notna(raw_frame) else 0
                        except (ValueError, TypeError):
                            clean_frame = 0
                            
                        clean_vid = str(row.get("Video", "")) if pd.notna(row.get("Video")) else st.session_state.current_video
                        clean_out = str(row.get("Outcome", "Unclassified")) if pd.notna(row.get("Outcome")) else "Unclassified"
                        
                        if row.get("🔍 Go To", False) == True:
                            target_frame = clean_frame
                            target_vid = clean_vid
                            
                        new_events.append({
                            "Video": clean_vid,
                            "Outcome": clean_out,
                            "Frame": clean_frame,
                            "Conflict": get_conflict_status(clean_vid, clean_out)
                        })
                        
                    if seek_triggered:
                        st.session_state.ledger_key += 1 
                        
                        if target_vid and target_vid != st.session_state.current_video:
                            switch_to_video(target_vid)
                            
                        st.session_state.frame_number = target_frame
                        st.session_state.is_playing = False 
                        reset_play_timer()
                        
                        st.session_state.session_events = new_events
                        st.rerun() 
                        
                    elif new_events != st.session_state.session_events:
                        st.session_state.session_events = new_events
                        st.session_state.data_is_saved = False
                        st.rerun()

                st.markdown("---")
                st.markdown("**Manual Export:**")
                
                anim_id = st.session_state.animal_id.strip()
                missing_id = anim_id == ""
                
                if missing_id:
                    st.error("🚨 Missing Animal ID: Enter an ID above to unlock saving.")
                    btn_text = "🔒 Enter Animal ID to Save"
                else:
                    btn_text = "💾 Download Current Session to Save"

                date_str = st.session_state.last_vid_date if st.session_state.last_vid_date else "000000"
                yymmdd = date_str[2:] if len(date_str) == 8 else date_str 
                session_id = st.session_state.current_session if st.session_state.current_session else "unknownSession"
                
                manual_filename = f"{yymmdd}_{session_id}_{anim_id if not missing_id else 'MISSING_ID'}_behaviorCounts.csv"
                
                if st.session_state.session_events:
                    df_manual_save = pd.DataFrame(st.session_state.session_events) 
                else:
                    df_manual_save = pd.DataFrame(columns=["Video", "Outcome", "Frame", "Conflict"])
                    
                df_manual_save["Total_Attempts"] = att
                df_manual_save["Total_Success"] = succ
                df_manual_save["Total_Fail"] = fail
                df_manual_save["Success_Rate_%"] = round(rate, 1)
                manual_csv_data = df_manual_save.to_csv(index=False)
                
                st.download_button(
                    label=btn_text,
                    data=manual_csv_data if not missing_id else "",
                    file_name=manual_filename if not missing_id else "locked.csv",
                    mime="text/csv",
                    width="stretch",
                    on_click=mark_as_saved,
                    disabled=missing_id 
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