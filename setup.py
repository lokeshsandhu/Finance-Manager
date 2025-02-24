from flask import Blueprint, render_template, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os, json

setup_bp = Blueprint('setup', __name__)

# Google Sheets Setup (shared)
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

@setup_bp.route("/setup", methods=["GET", "POST"])
def setup_route():
    if request.method == "GET":
        return render_template("setup.html")
    else:
        try:
            # Parse form data into a list of banks with accounts.
            banks = request.form.getlist("bank[]")
            setup_data = []
            for i, bank_name in enumerate(banks):
                account_types = request.form.getlist(f"account_type_{i}[]")
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
            # Header row: ["Bank Name", "Account Type", "Current Balance"]
            final_matrix = []
            final_matrix.append(["Bank Name", "Account Type", "Current Balance"])
            grand_total = 0.0

            # For each bank, list accounts then add a Total row.
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
