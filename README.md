# 🔮 Owen Tarot AI

A modern tarot reading web app powered by AI.
Draw cards, receive deep interpretations, and chat with Owen for further insights — just like a real tarot session.

---

## ✨ Features

* 🔮 Draw 1 / 3 / 10 tarot cards
* 🔁 Upright & Reversed cards
* 🤖 AI-powered tarot interpretation
* 💬 Chat with Owen AI for deeper analysis
* 📱 Responsive design (PC & Mobile)
* 🗂️ SQLite storage for session/history

---

## 🚀 Live Demo

👉 (Add your link here after deploy)
`https://your-app.onrender.com`

---

## 🛠️ Tech Stack

* Python (Flask)
* HTML / CSS / JavaScript
* SQLite
* OpenAI API

---

## ⚙️ Setup & Run Locally

### 1. Clone repository

```bash
git clone https://github.com/OwenDevelopment/Owen-Tarot-AI.git
cd Owen-Tarot-AI
```

### 2. Create virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env` file

```env
OPENAI_API_KEY=your_api_key_here
SECRET_KEY=your_secret_key_here
```

### 5. Run app

```bash
python app.py
```

👉 Open: http://127.0.0.1:5000

---

## ☁️ Deployment (Render)

* Create Web Service on Render
* Build command:

```bash
pip install -r requirements.txt
```

* Start command:

```bash
gunicorn app:app
```

* Add Environment Variables:

  * `OPENAI_API_KEY`
  * `SECRET_KEY`

---

## 📁 Project Structure

```
Owen-Tarot-AI/
│── app.py
│── config.py
│── requirements.txt
│── tarot_data.json
│── card_data.json
│
├── services/
│   ├── ai_service.py
│   ├── db_service.py
│   └── tarot_service.py
│
├── templates/
│   └── index.html
│
├── static/
│   └── style.css
```

---

## 🔐 Security Notes

* `.env` is not included in the repository
* Never expose your API keys publicly
* Always regenerate keys if leaked

---

## 🎯 Future Improvements

* Card flip animations
* More tarot spreads
* User accounts
* Save reading history
* Better AI personalization

---

## 👨‍💻 Author

**OwenDevelopment**

---

## ⭐ If you like this project

Give it a star ⭐ on GitHub!
