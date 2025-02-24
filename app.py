from flask import Flask, request, render_template
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Load Google Sheets credentials from environment variable
creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("Finance Manager").sheet1

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    data = request.form
    sheet.append_row([data["date"], data["type"], data["bank"], data["account"], data["amount"], data["purpose"], data["place"]])
    return "Transaction Added!"

@app.route("/view_transactions")
def view_transactions():
    records = sheet.get_all_records()
    return {"transactions": records}

@app.route("/delete_transaction", methods=["POST"])
def delete_transaction():
    transaction_id = int(request.form["id"])
    sheet.delete_rows(transaction_id + 1)  # Adjust for header row
    return "Transaction Deleted!"

if __name__ == "__main__":
    app.run(debug=True)
