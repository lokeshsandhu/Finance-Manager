from flask import Flask, request, jsonify, render_template
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("Finance Manager").sheet1  # Make sure this matches your Google Sheet name

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    try:
        data = request.form
        sheet.append_row([data["date"], data["type"], data["bank"], data["account"], data["amount"], data["purpose"], data["place"]])
        return jsonify({"message": "Transaction Added Successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error adding transaction", "error": str(e)}), 500

@app.route("/view_transactions")
def view_transactions():
    try:
        transactions = sheet.get_all_records()
        return jsonify({"transactions": transactions}), 200
    except Exception as e:
        return jsonify({"message": "Error fetching transactions", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
