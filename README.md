# 🐁 Neural Behavioral Analyzer

A sleek, browser-based frame-by-frame video analyzer and behavioral logging tool built with Python and Streamlit. 

This tool is designed to streamline the manual classification of animal behavioral tasks (e.g., reaching tasks) by combining a robust video player with an integrated data-entry system. It automatically groups videos by session, tracks per-video outcomes to prevent double-counting, and exports your session data as clean CSV files.

## ✨ Features
* **Modern Web Interface:** Replaces clunky desktop GUI frameworks with a responsive web app.
* **Frame-by-Frame Control:** Scrub through videos with absolute precision or play them at a controlled 10 FPS.
* **Dynamic Resizing:** Adjust the video display size on the fly without losing resolution or aspect ratio.
* **Smart Session Tracking:** Automatically detects when you switch to a new animal/session and prompts you to save the previous session's data.
* **Per-Video Classification:** Mark a video as `Success`, `Fail`, or `Ignore` (non-attempts). The software ensures no video is counted twice.
* **Real-time Statistics:** Calculates total attempts and success rates dynamically as you log videos.

---

## 🛠️ Installation & Setup

**1. Clone the repository (or download the script)**
Ensure you have the main `app.py` script saved on your local machine.

**2. Install dependencies**
This app requires Python 3.8+ and a few external libraries. Open your terminal or Anaconda prompt and run:
`pip install streamlit opencv-python pandas`
*(Note: Streamlit version 1.34 or higher is required for the popup dialog features.)*

**3. Run the application**
Navigate to the folder containing the script and run:
`streamlit run app.py`
A new tab will automatically open in your default web browser displaying the app. To shut down the app, go back to your terminal and press `Ctrl + C`.

---

## 📂 Required File Naming Convention

For the automatic session-tracking to work, your video files **must** follow this naming convention:
`v_YYYYMMDD_sessionXXX_anything_else.mp4`

**Examples:**
* `v_20251125_session001_012032_reach_fail.mp4`
* `v_20251125_session002_147848_stim_success.mp4`

The app splits the filename by underscores (`_`). It expects the **date** to be in the second position and the **session ID** to be in the third position.

---

## 🚀 How to Use the Analyzer

1. **Load Your Folder:**
   At the top of the app, paste the absolute path to the directory containing your video files and press `Enter`. The playlist on the right will automatically populate.

2. **Start a Session:**
   * Click the first video in the playlist for your target session.
   * In the middle **Session Data** column, type in the **Animal ID** (e.g., `Mouse_12`).

3. **Analyze the Video:**
   * Use the **Play/Pause** button, the **Scrub** slider, or the **Jump to frame** input to analyze the behavior.
   * Adjust the video size using the slider directly above the video if it is too large for your monitor.

4. **Classify the Behavior:**
   In the middle column, click one of the classification buttons:
   * **✅ Success:** Logs an attempt and a success.
   * **❌ Fail:** Logs an attempt and a failure.
   * **🚫 Ignore:** Marks the video as a non-attempt (does not add to the attempt total).
   * *Note: You can safely change your mind. Clicking a new button overwrites the previous classification for that specific video.*

5. **Save the Data:**
   When you finish classifying all videos for the current session, simply click the first video of the **next session** in the playlist. 
   * The app will instantly pause and freeze.
   * A popup dialog will appear prompting you to download the finalized `.csv` file for the session you just completed.
   * The exported file will be automatically named: `YYMMDD_AnimalID_behaviorCounts.csv`.

---

## 📊 CSV Export Format

The exported CSV file contains a single, clean row of summary data ready to be imported into Excel, R, or Python for further analysis:

| Attempt | Success | Fail | Success Rate |
| :--- | :--- | :--- | :--- |
| 15 | 10 | 5 | 66.67 |
