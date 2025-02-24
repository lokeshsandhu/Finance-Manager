from flask import Flask, request, jsonify, render_template
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("Finance Manager").sheet1  # Ensure this matches your Google Sheet name

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
        formatted_transactions = []
        for idx, t in enumerate(transactions):
            formatted_transactions.append({
                "id": idx + 1,
                "date": t.get("Date", ""),
                "type": t.get("Type", ""),
                "bank": t.get("Bank", ""),
                "account": t.get("Account", ""),
                "amount": t.get("Amount", ""),
                "purpose": t.get("Purpose", ""),
                "place": t.get("Place", "")
            })
        return jsonify({"transactions": formatted_transactions}), 200
    except Exception as e:
        return jsonify({"message": "Error fetching transactions", "error": str(e)}), 500

@app.route("/delete_transaction", methods=["POST"])
def delete_transaction():
    try:
        transaction_id = int(request.form["id"])
        sheet.delete_rows(transaction_id + 1)  # Adjust for header row
        return jsonify({"message": "Transaction Deleted Successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error deleting transaction", "error": str(e)}), 500

@app.route("/edit_transaction", methods=["POST"])
def edit_transaction():
    try:
        transaction_id = int(request.form["id"])
        new_amount = request.form["amount"]
        sheet.update_cell(transaction_id + 1, 5, new_amount)  # Amount is in column 5
        return jsonify({"message": "Transaction Edited Successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error editing transaction", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
