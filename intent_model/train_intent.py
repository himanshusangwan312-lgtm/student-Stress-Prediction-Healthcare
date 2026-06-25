import pandas as pd
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Load dataset
df = pd.read_csv("intent_dataset.csv")

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    df["text"], df["intent"], test_size=0.2, random_state=42
)

# Vectorization
vectorizer = TfidfVectorizer()
X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

# Model
model = LogisticRegression(max_iter=200)
model.fit(X_train_vec, y_train)

# Evaluation
y_pred = model.predict(X_test_vec)
accuracy = accuracy_score(y_test, y_pred)

print("Model Training Completed")
print("Accuracy:", accuracy)

# Save model
pickle.dump(model, open("intent_model.pkl", "wb"))
pickle.dump(vectorizer, open("vectorizer.pkl", "wb"))

print("Model and Vectorizer saved successfully")