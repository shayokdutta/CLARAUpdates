# 🐁 Reach Behavioral Analyzer

![Behavioral Analyzer UI](images/BehavioralAnalyzer.png)

A high-performance, browser-based frame-by-frame video analyzer and behavioral logging tool built with Python and Streamlit. 

Optimized for high-speed camera data (e.g., 150+ FPS), this tool is designed to streamline the manual classification of animal reaching tasks. It utilizes in-memory RAM caching and image compression to provide lag-free, zero-buffer video scrubbing directly in your web browser. It automatically scans your directories to build a collapsible date/session hierarchy, audits manual curation against automated neural network labels, and provides bulletproof data-saving features to prevent accidental data loss in the lab.

## ✨ Key Features
* **High-Speed RAM Caching:** Bypasses slow hard-drive and WebSocket bottlenecks by pre-loading and compressing video frames directly into memory for lightning-fast scrubbing.
* **Dynamic Playback Speed:** Natively reads your camera's capture rate (e.g., 150 FPS) and provides a slider to adjust slow-motion playback on the fly without altering the raw data.
* **Smart Directory Scanning:** Point the app to a root folder (e.g., `learning/`) and it will automatically map out all subfolders, building a clean, nested hierarchy of Dates ➡️ Sessions ➡️ Videos.
* **Keyboard Hotkeys:** A fully integrated JavaScript listener allows you to classify behaviors, scrub frames, and navigate the playlist without ever touching your mouse.
* **Workspace Management:** Live progress tracking and session-locking. Your Animal ID locks once you start curating to prevent typos, and you can cleanly "Close" a session when finished to clear your workspace.
* **Automated Curation Auditing:** Automatically compares your manual label against the automated neural network label in the video's filename, flagging mismatches for easy auditing.
* **Live Editable Dataframes:** Fix classification mistakes on the fly by double-clicking directly inside the app's raw data table.

---

## ⌨️ Keyboard Shortcuts

The app features a silent background listener that intercepts keystrokes to maximize curation speed. *(Note: Hotkeys are automatically disabled while you are typing inside a text box).*

| Action | Key |
| :--- | :--- |
| **Play / Pause** | `Spacebar` |
| **Previous Frame** | `Left Arrow` |
| **Next Frame** | `Right Arrow` |
| **Previous Video** (in session) | `Up Arrow` |
| **Next Video** (in session) | `Down Arrow` |
| **Classify: Success** | `S` |
| **Classify: Fail** | `F` |
| **Classify: Ignore** | `I` |

---

## 🛠️ Installation & Setup

**1. Clone the repository**
Ensure you have the main `app.py` script saved on your local machine.

**2. Install dependencies**
This app requires Python 3.8+ and a few external libraries. *Note: Streamlit version 1.46.0 or higher is required for the nested date/session folders to display correctly.*
```bash
pip install --upgrade streamlit opencv-python pandas