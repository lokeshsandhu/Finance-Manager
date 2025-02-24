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
        return jsonify({"transactions": transactions}), 200
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
        new_data = [
            request.form["date"], request.form["type"], request.form["bank"], request.form["account"],
            request.form["amount"], request.form["purpose"], request.form["place"]
        ]
        sheet.update(f"A{transaction_id + 1}:G{transaction_id + 1}", [new_data])
        return jsonify({"message": "Transaction Edited Successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error editing transaction", "error": str(e)}), 500

@app.route("/refund_transaction", methods=["POST"])
def refund_transaction():
    try:
        transaction_id = int(request.form["id"])
        refund_amount = float(request.form["refund_amount"])
        original_data = sheet.row_values(transaction_id + 1)
        new_amount = float(original_data[4]) - refund_amount
        refund_status = f"Partial Refund: {refund_amount}" if new_amount > 0 else "Full Refund"
        sheet.update_cell(transaction_id + 1, 5, new_amount)
        sheet.update_cell(transaction_id + 1, 8, refund_status)  # Assume column H is for refund status
        return jsonify({"message": "Refund Processed Successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error processing refund", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
