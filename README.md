# 🐁 Reach Behavioral Analyzer

![Behavioral Analyzer UI](images/BehavioralAnalyzer.png)

A sleek, browser-based frame-by-frame video analyzer and behavioral logging tool built with Python and Streamlit. 

This tool is designed to streamline the manual classification of animal reaching tasks. It combines a robust video player with an integrated data-entry system, automatically scans your directories to group videos by date and session, audits manual curation against automated neural network labels, and provides bulletproof data-saving features to prevent accidental data loss in the lab.

## ✨ Key Features
* **Modern Web Interface:** Replaces clunky desktop GUI frameworks with a responsive web app.
* **Smart Directory Scanning:** Point the app to a root folder (e.g., `learning/`) and it will automatically map out all subfolders, building a clean, collapsible hierarchy of Dates ➡️ Sessions ➡️ Videos.
* **Workspace Management:** Live progress tracking (e.g., `4/15 categorized`) and session-locking. Your Animal ID locks once you start curating to prevent typos, and you can cleanly "Close" a session when finished to clear your workspace.
* **Automated Curation Auditing (Conflict Detection):** Automatically compares your manual label against the automated neural network label in the video's filename, flagging mismatches for easy auditing.
* **Live Editable Dataframes:** Fix classification mistakes on the fly by double-clicking directly inside the app's raw data table.
* **Seamless Session Resuming:** Upload a previously saved CSV to instantly restore your session's exact state, including all previous classifications and the Animal ID.
* **Overwrite & Data Loss Protection:** Built-in safeguards prevent you from closing an unsaved session, switching videos without saving, or accidentally overwriting an existing animal's data file without explicit confirmation.

---

## 🛠️ Installation & Setup

**1. Clone the repository**
Ensure you have the main `app.py` script saved on your local machine.

**2. Install dependencies**
This app requires Python 3.8+ and a few external libraries. Open your terminal or Anaconda prompt and run:
`pip install streamlit opencv-python pandas`

**3. Run the application**
Navigate to the folder containing the script and run:
`streamlit run app.py`
A new tab will automatically open in your default web browser displaying the app. To shut down the app, go back to your terminal and press `Ctrl + C`.

---

## 📂 Required File & Folder Naming Convention

**Folder Structure:** The app supports nested directories. It is recommended to have a root folder (e.g., `learning/`) containing subfolders for each date (e.g., `20251125/`).

**Video Files:** For the automatic session-tracking and conflict-detection to work, your video files **must** follow this naming convention:
`v_YYYYMMDD_sessionXXX_anything_else_automatedLabel.mp4`

**Examples:**
* `v_20251125_session001_012032_reach_fail.mp4`
* `v_20251125_session002_147848_stim_success.mp4`

The app splits the filename by underscores (`_`). It expects:
1. The **date** to be in the second position.
2. The **session ID** to be in the third position.
3. The **automated label** (e.g., `success` or `fail`) to be at the very end of the filename before the `.mp4` extension.

---

## 🚀 How to Use the Analyzer

### 1. Load Your Directory
At the top of the app, paste the absolute path to your root directory (e.g., `.../learning/`) and press `Enter`. The playlist on the right will automatically build a collapsible tree of all dates and sessions found inside.

### 2. Start or Resume a Session
* **New Session:** Expand a session folder in the playlist and click the first video. In the middle **Session Data** column, type in the **Animal ID** (e.g., `Mouse_12`).
* **Resume Session:** Use the "Upload CSV to Resume Data" box at the top of the middle column. The app will automatically fill in the Animal ID, load your previous classifications, and jump to the correct video.

### 3. Analyze and Classify
* Use the video controls to analyze the behavior frame-by-frame. 
* Click one of the classification buttons: **✅ Success**, **❌ Fail**, or **🚫 Ignore**. 
* The video will automatically advance, your progress bar will update, and the **Animal ID will lock** to prevent accidental changes.
* *Note: To fix a mistake, scroll down to the "Editable Raw Data" table and double-click the outcome cell to change it. The summary stats will instantly recalculate.*

### 4. The "Conflict" Column (Data Auditing)
The software automatically audits your manual label against the filename's automated neural network label:
* **`0` (Match):** Your manual label matches the neural network's label.
* **`1` (Conflict):** Your manual label disagrees with the neural network, or you marked the video as `Ignore`.

### 5. Saving & Closing Your Workspace
The app tracks unsaved modifications for you.
* **Save & Close:** When you finish an animal, click the **❌ Close** button next to the Animal ID. If you haven't saved, a popup will force you to save the `.csv` file directly into the video's original subfolder before clearing the screen.
* **Auto-Prompt:** If you try to jump to a different session in the playlist without saving your current one, the app will freeze and prompt you to save first.
* **Manual Export:** You can click "Download Current Session to Save" at any time to download a backup CSV directly to your browser's default downloads folder.

---

## 📊 CSV Export Format

The exported CSV file contains a complete raw log followed by the session summary totals. It is fully compatible with Excel, R, Python, and the app's own resume feature:

| Video | Outcome | Conflict | Total_Attempts | Total_Success | Total_Fail | Success_Rate_% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| v_20251125_session001_01_reach_fail.mp4 | Fail | 0 | 15 | 10 | 5 | 66.7 |
| v_20251125_session001_02_stim_success.mp4 | Fail | 1 | 15 | 10 | 5 | 66.7 |
| v_20251125_session001_03_reach_fail.mp4 | Ignore | 1 | 15 | 10 | 5 | 66.7 |