import random

def chatbot_reply(message):

    msg = message.lower()

    # ---------- GREETING ----------
    if any(word in msg for word in ["hello","hi","hey","hlo"]):
        return "Hello 🙂 How can I help you? You can ask about stress, study, anxiety."

    # ---------- STRESS ----------
    elif "stress" in msg:
        return "Try deep breathing, short walk, and talk to a friend. If stress is high, consider counselling."

    # ---------- DEPRESSION ----------
    elif "depress" in msg or "sad" in msg:
        return "You are not alone. Try to speak with someone you trust. Professional counselling can help."

    # ---------- STUDY ----------
    elif "study" in msg or "exam" in msg:
        return "Use Pomodoro method: study 25 minutes, break 5 minutes. Avoid phone during study."

    # ---------- ANXIETY ----------
    elif "anxiety" in msg or "panic" in msg:
        return "Slow breathing helps anxiety. Inhale 4 sec, hold 4 sec, exhale 4 sec."

    # ---------- THANKS ----------
    elif "thank" in msg:
        return "You're welcome 🙂 Stay strong and take care."

    # ---------- DEFAULT ----------
    else:
        return "I understand. Can you explain more? You can ask about stress, study, anxiety, depression."
