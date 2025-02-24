from flask import Flask, request, jsonify, render_template
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os, json, datetime

app = Flask(__name__)

# ---------------------------
#  Google Sheets Setup
# ---------------------------
scope = [
    "https://spreadsheets.google.com/feeds", 
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file", 
    "https://www.googleapis.com/auth/drive"
]

creds_json = os.getenv("GOOGLE_CREDENTIALS")
if not creds_json:
    raise Exception("GOOGLE_CREDENTIALS not set.")

creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)
client = gspread.authorize(creds)

# Open main transaction sheet (ensure a sheet named "Finance Manager" exists)
try:
    sheet = client.open("Finance Manager").sheet1  
except Exception as e:
    raise Exception("Main transaction sheet not found. Ensure a sheet named 'Finance Manager' exists.") from e

# ---------------------------
#  Home / Main Page Route
# ---------------------------
@app.route("/")
def home():
    try:
        # Load banks and accounts from the "banking information" worksheet.
        try:
            bank_sheet = client.open("Finance Manager").worksheet("banking information")
            # Assume the sheet format is as follows:
            # Row1: Header: ["Bank Name", bank1, bank2, ...]
            # Row3-5: Account types and values for each bank (if available)
            bank_headers = bank_sheet.row_values(1)  # e.g., ["Bank Name", "BMO", "RBC", "CIBC", "Cash"]
            banks_data = {}
            # We'll grab account names from rows 3-5 for each bank (skip header cell)
            for col_index, bank in enumerate(bank_headers[1:], start=1):
                if bank:
                    col_values = bank_sheet.col_values(col_index+1)
                    # We assume account rows start at row 3 (index 2) and go until row 5 (index 4)
                    accounts = col_values[2:5]
                    # Remove empty cells
                    banks_data[bank] = [a for a in accounts if a]
            return render_template("index.html", default_date=datetime.date.today().isoformat(), banks=banks_data)
        except gspread.exceptions.WorksheetNotFound:
            # No setup data available yet.
            return render_template("index.html", default_date=datetime.date.today().isoformat(), banks={})
    except Exception as e:
        return render_template("index.html", default_date=datetime.date.today().isoformat(), banks={}, error=str(e))

# ---------------------------
#  Add Transaction Route
# ---------------------------
@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    try:
        data = request.form
        # Determine transaction direction: Outgoing amounts are negative.
        direction = data.get("transaction_direction", "Outgoing")
        amount = float(data["amount"])
        if direction == "Outgoing":
            amount = -abs(amount)
        else:
            amount = abs(amount)
        # Expected headers in main sheet: Date, Time, Type, Bank, Account, Direction, Amount, Purpose
        row = [
            data["date"],
            data["time"],
            data["type"],
            data.get("bank", ""),
            data.get("account", ""),
            direction,
            amount,
            data["purpose"]
        ]
        sheet.append_row(row)
        return jsonify({"message": "Transaction Added Successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error adding transaction", "error": str(e)}), 500

# ---------------------------
#  View Transactions Route
# ---------------------------
@app.route("/view_transactions")
def view_transactions():
    try:
        transactions = sheet.get_all_records()
        formatted_transactions = []
        # Expected keys: Date, Time, Type, Bank, Account, Direction, Amount, Purpose
        for t in transactions:
            formatted_transactions.append({
                "date": t.get("Date", ""),
                "time": t.get("Time", ""),
                "type": t.get("Type", ""),
                "bank": t.get("Bank", ""),
                "account": t.get("Account", ""),
                "direction": t.get("Direction", ""),
                "amount": t.get("Amount", ""),
                "purpose": t.get("Purpose", "")
            })
        return jsonify({"transactions": formatted_transactions}), 200
    except Exception as e:
        return jsonify({"message": "Error fetching transactions", "error": str(e)}), 500

# ---------------------------
#  Search Transactions Route (Optional)
# ---------------------------
@app.route("/search_transactions")
def search_transactions():
    try:
        keyword = request.args.get("keyword", "").lower()
        transactions = sheet.get_all_records()
        filtered = []
        for t in transactions:
            combined = " ".join(str(value) for value in t.values()).lower()
            if keyword in combined:
                filtered.append({
                    "date": t.get("Date", ""),
                    "time": t.get("Time", ""),
                    "type": t.get("Type", ""),
                    "bank": t.get("Bank", ""),
                    "account": t.get("Account", ""),
                    "direction": t.get("Direction", ""),
                    "amount": t.get("Amount", ""),
                    "purpose": t.get("Purpose", "")
                })
        return jsonify({"transactions": filtered}), 200
    except Exception as e:
        return jsonify({"message": "Error searching transactions", "error": str(e)}), 500

# ---------------------------
#  Setup Route
# ---------------------------
@app.route("/setup", methods=["GET", "POST"])
def setup_route():
    if request.method == "GET":
        return render_template("setup.html")
    else:
        try:
            # Parse form data to build setup_data.
            banks = request.form.getlist("bank[]")
            setup_data = []
            for i, bank_name in enumerate(banks):
                account_types  = request.form.getlist(f"account_type_{i}[]")
                account_balances = request.form.getlist(f"account_balance_{i}[]")
                accounts = []
                for acc_type, acc_balance in zip(account_types, account_balances):
                    accounts.append({
                        "type": acc_type,
                        "balance": acc_balance
                    })
                setup_data.append({
                    "bank": bank_name,
                    "accounts": accounts
                })

            # Build the final matrix for the desired layout.
            # Layout:
            # Row 1: ["Bank Name", "Account Type", "Current Balance"]
            # Then, for each bank, one row per account (first row shows bank name, others blank),
            # then a "Total (Bank Name)" row, and finally a "Grand Total (All Banks)" row.
            final_matrix = []
            final_matrix.append(["Bank Name", "Account Type", "Current Balance"])
            grand_total = 0.0
            for bank_info in setup_data:
                bank_name = bank_info["bank"]
                bank_accounts = bank_info["accounts"]
                bank_total = 0.0
                first_row = True
                for acc in bank_accounts:
                    row = []
                    if first_row:
                        row.append(bank_name)
                        first_row = False
                    else:
                        row.append("")
                    row.append(acc["type"])
                    balance_val = float(acc["balance"] or 0.0)
                    row.append(balance_val)
                    bank_total += balance_val
                    final_matrix.append(row)
                final_matrix.append([f"Total ({bank_name})", "", bank_total])
                grand_total += bank_total
            final_matrix.append([f"Grand Total (All Banks)", "", grand_total])

            # Update or create the "banking information" worksheet.
            try:
                bank_sheet = client.open("Finance Manager").worksheet("banking information")
                bank_sheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                bank_sheet = client.open("Finance Manager").add_worksheet(title="banking information", rows="100", cols="20")
            bank_sheet.update("A1", final_matrix)

            return jsonify({"message": "Setup data saved successfully!", "data": setup_data}), 200

        except Exception as e:
            return jsonify({"message": "Error saving setup data", "error": str(e)}), 500

# ---------------------------
#  Run Flask
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
