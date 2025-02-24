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

# Open main transaction sheet
sheet = client.open("Finance Manager").sheet1  

# ------------------ Main Page ------------------
@app.route("/")
def home():
    try:
        # Load banks and accounts from the "banking information" worksheet
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
        sheet.append_row([
            data["date"], data["time"], data["type"], 
            data.get("bank", ""), data.get("account", ""), 
            data["amount"], data["purpose"], data.get("balance_left", ""), ""
        ])
        return jsonify({"message": "Transaction Added Successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error adding transaction", "error": str(e)}), 500

# ------------------ Setup Page ------------------
@app.route("/setup", methods=["GET", "POST"])
def setup():
    if request.method == "GET":
        return render_template("setup.html")
    else:
        try:
            # Get user input from Setup page
            banks = request.form.getlist("bank[]")
            setup_data = []
            for i, bank in enumerate(banks):
                account_names = request.form.getlist(f"account_name_{i}[]")
                account_balances = request.form.getlist(f"account_balance_{i}[]")
                accounts = []
                for name, balance in zip(account_names, account_balances):
                    accounts.append({"name": name, "balance": balance})
                setup_data.append({"bank": bank, "accounts": accounts})

            # Save to Google Sheets in a worksheet named "banking information"
            try:
                bank_sheet = client.open("Finance Manager").worksheet("banking information")
                bank_sheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                bank_sheet = client.open("Finance Manager").add_worksheet(title="banking information", rows="100", cols="20")

            # Prepare data for Google Sheets
            bank_names = [b["bank"] for b in setup_data]
            data_matrix = [bank_names]
            max_accounts = max(len(b["accounts"]) for b in setup_data) if setup_data else 0
            for j in range(max_accounts):
                row = []
                for b in setup_data:
                    row.append(b["accounts"][j]["name"] if j < len(b["accounts"]) else "")
                data_matrix.append(row)

            # Update Google Sheet
            bank_sheet.update("A1", data_matrix)

            return jsonify({"message": "Setup saved!", "data": setup_data}), 200
        except Exception as e:
            return jsonify({"message": "Error saving setup", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
