from flask import Flask, request, jsonify, render_template
import os, json, datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", 
         "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", 
         "https://www.googleapis.com/auth/drive"]
creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("Finance Manager").sheet1  # Main transaction sheet

# Helper: get current row number (adjusting for header row)
def get_sheet_row(transaction_id):
    return transaction_id + 1  # assuming header is row 1

@app.route("/")
def home():
    # Pass default date to the template
    today = datetime.date.today().isoformat()
    return render_template("index.html", default_date=today)

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    try:
        data = request.form
        # Append new transaction (fields: date, type, bank, account, amount, purpose, place)
        sheet.append_row([
            data["date"], 
            data["type"], 
            data["bank"], 
            data["account"], 
            data["amount"], 
            data["purpose"], 
            data["place"]
        ])
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
                "place": t.get("Place", ""),
                "refund_status": t.get("Refund Status", "")  # New column for refund info
            })
        return jsonify({"transactions": formatted_transactions}), 200
    except Exception as e:
        return jsonify({"message": "Error fetching transactions", "error": str(e)}), 500

@app.route("/edit_transaction", methods=["POST"])
def edit_transaction():
    try:
        transaction_id = int(request.form["id"])
        # Retrieve all editable fields from the request
        data = request.form
        updated_row = [
            data["date"],
            data["type"],
            data["bank"],
            data["account"],
            data["amount"],
            data["purpose"],
            data["place"]
        ]
        row_number = get_sheet_row(transaction_id)
        # Update the entire row in the sheet (columns A-G)
        sheet.update(f"A{row_number}:G{row_number}", [updated_row])
        return jsonify({"message": "Transaction Edited Successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error editing transaction", "error": str(e)}), 500

@app.route("/delete_transaction", methods=["POST"])
def delete_transaction():
    try:
        transaction_id = int(request.form["id"])
        row_number = get_sheet_row(transaction_id)
        sheet.delete_rows(row_number)
        return jsonify({"message": "Transaction Deleted Successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error deleting transaction", "error": str(e)}), 500

@app.route("/refund_transaction", methods=["POST"])
def refund_transaction():
    try:
        transaction_id = int(request.form["id"])
        refund_amount = request.form.get("refund_amount", None)
        refund_type = request.form.get("refund_type", "full")  # full or partial
        row_number = get_sheet_row(transaction_id)
        # Mark the transaction as refunded. Here we update an 8th column "Refund Status".
        refund_status = f"Refunded ({refund_type})"
        sheet.update_cell(row_number, 8, refund_status)
        return jsonify({"message": "Transaction marked as refunded!"}), 200
    except Exception as e:
        return jsonify({"message": "Error processing refund", "error": str(e)}), 500

@app.route("/search_transactions")
def search_transactions():
    try:
        keyword = request.args.get("keyword", "").lower()
        date_filter = request.args.get("date", "")
        bank_filter = request.args.get("bank", "").lower()
        transactions = sheet.get_all_records()
        filtered = []
        for idx, t in enumerate(transactions):
            # Simple search across all fields and filters
            t_str = " ".join([str(v) for v in t.values()]).lower()
            if keyword and keyword not in t_str:
                continue
            if date_filter and t.get("Date", "") != date_filter:
                continue
            if bank_filter and bank_filter not in t.get("Bank", "").lower():
                continue
            filtered.append({
                "id": idx + 1,
                "date": t.get("Date", ""),
                "type": t.get("Type", ""),
                "bank": t.get("Bank", ""),
                "account": t.get("Account", ""),
                "amount": t.get("Amount", ""),
                "purpose": t.get("Purpose", ""),
                "place": t.get("Place", ""),
                "refund_status": t.get("Refund Status", "")
            })
        return jsonify({"transactions": filtered}), 200
    except Exception as e:
        return jsonify({"message": "Error searching transactions", "error": str(e)}), 500

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if request.method == "GET":
        # Render a setup page where users can choose banks, account types, categories, etc.
        return render_template("setup.html")
    else:
        try:
            # Save setup preferences (for simplicity, this could be stored in another Google Sheet or a config file)
            data = request.form
            # Example: data might include a JSON string of banks, accounts, and categories.
            # Save or process the data as needed.
            return jsonify({"message": "Setup preferences saved!"}), 200
        except Exception as e:
            return jsonify({"message": "Error saving setup preferences", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
