# Garmin AI Coach 🏃‍♂️🤖

> **"The LLM didn't know my training history. My Garmin did. So I connected them."**

## 📖 The Story
Last week, I faced one of the biggest fears in marathon training.

Only 7 weeks before the Tel Aviv Marathon, I finished a 33k long run with an uncomfortable feeling in my Achilles. Like almost everyone today, I tried to consult an LLM for advice.

**But I realized the LLM is missing a lot of data.**
It doesn't know my last workouts, my weekly balance, my body metrics, or my specific goal (3:14 pace).

**Do you know who does? My Garmin watch.**

So the solution was simple: I wrote a Python tool that lets the LLM pull this information, analyze my condition, and **push** adapted workouts directly to my training calendar.

## 🚀 What This Project Does
This is an agentic workflow that connects the **Garmin Connect API** with **LLM reasoning**.

1.  **Pulls Data:** Fetches my actual recent runs, heart rate, and training load from Garmin.
2.  **Analyzes Context:** Feeds the specific biometric data + my marathon goals into the LLM.
3.  **Acts:** Creates a structured workout file and uploads it back to my watch for the next training session.

## 🛠️ Tech Stack
* **Python** (Core logic)
* **Streamlit** (UI & Visualization)
* **Garmin Connect API** (Data ingestion & workout upload)
* **OpenAI API / LLM** (Reasoning & planning)

## 🏃‍♂️ How to Run It

### 1. Installation
```bash
# Clone the repo
git clone [https://github.com/avivyossef29/garmin-ai-coach.git](https://github.com/avivyossef29/garmin-ai-coach.git)
cd garmin-ai-coach

# Create virtual env & install dependencies
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 2. Configuration
Create a file named .env in the root directory and add your keys:
```bash
# .env file
GARMIN_EMAIL=your_email@example.com
GARMIN_PASSWORD=your_password
OPENAI_API_KEY=sk-proj-...
```

### 3. Run the App
```bash
./venv/bin/streamlit run app.py
```

### 👨‍💻 About Me
I'm Aviv Yossef, an M.Sc. Computer Science student at Tel Aviv University. I built this because I believe AI agents should be grounded in real-world data, not just text. (And because I really want to make it to the starting line in Tel Aviv!)

See you at the Marathon! 