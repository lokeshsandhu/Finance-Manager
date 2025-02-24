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

# Main Transactions Sheet
sheet = client.open("Finance Manager").sheet1  

# ------------------ Main Page ------------------
@app.route("/")
def home():
    try:
        # Load banks and accounts from "banking information" worksheet
        try:
            bank_sheet = client.open("Finance Manager").worksheet("banking information")
        except gspread.exceptions.WorksheetNotFound:
            return render_template("index.html", default_date=datetime.date.today().isoformat(), banks={})

        # Read bank headers (row 1)
        bank_headers = bank_sheet.row_values(1)
        banks_data = {}

        # Read all accounts and balances
        accounts_data = bank_sheet.get_all_values()[1:]  # Skip header row
        for col_index, bank in enumerate(bank_headers):
            if bank:
                banks_data[bank] = []
                for row in accounts_data:
                    if row[col_index]:  # Only add if an account exists
                        banks_data[bank].append(row[col_index])

        return render_template("index.html", default_date=datetime.date.today().isoformat(), banks=banks_data)
    except Exception as e:
        return render_template("index.html", default_date=datetime.date.today().isoformat(), banks={}, error=str(e))

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    try:
        data = request.form

        # Determine if transaction is incoming or outgoing
        transaction_type = data.get("transaction_direction", "Outgoing")
        amount = float(data["amount"])
        if transaction_type == "Outgoing":
            amount = -amount  # Deduct from balance

        # Update transaction sheet
        sheet.append_row([
            data["date"], data["time"], data["type"], 
            data.get("bank", ""), data.get("account", ""), 
            transaction_type, amount, data["purpose"], data.get("balance_left", ""), ""
        ])
        return jsonify({"message": "Transaction Added Successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error adding transaction", "error": str(e)}), 500

@app.route("/view_transactions")
@app.route("/view_transactions")
def view_transactions():
    try:
        transactions = sheet.get_all_records()  # Fetch data from Google Sheets
        formatted_transactions = []
        for t in transactions:
            formatted_transactions.append({
                "date": t.get("Date", ""),  
                "time": t.get("Time", ""),  
                "type": t.get("Type", ""),  
                "bank": t.get("Bank", ""),  
                "account": t.get("Account", ""),  
                "direction": t.get("Direction", ""),  
                "amount": t.get("Amount", ""),  
                "purpose": t.get("Purpose", ""),  
            })
        return jsonify({"transactions": formatted_transactions}), 200
    except Exception as e:
        return jsonify({"message": "Error fetching transactions", "error": str(e)}), 500


@app.route("/search_transactions")
def search_transactions():
    try:
        keyword = request.args.get("keyword", "").lower()
        transactions = sheet.get_all_records()
        filtered = [t for t in transactions if keyword in str(t).lower()]
        return jsonify({"transactions": filtered}), 200
    except Exception as e:
        return jsonify({"message": "Error searching transactions", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
