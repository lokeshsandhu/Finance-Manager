from flask import Flask, request, jsonify, render_template
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os, json

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

# ---------------------------
#  Setup Route
# ---------------------------
@app.route("/setup", methods=["GET", "POST"])
def setup():
    if request.method == "GET":
        # Render a template if needed, or just return some HTML
        return render_template("setup.html")
    else:
        try:
            # 1. Parse form data to build setup_data
            #    Example form structure:
            #    bank[] = ["ABC Bank", "XYZ Bank", ...]
            #    account_name_i[] / account_type_i[] / account_balance_i[] for each bank i
            banks = request.form.getlist("bank[]")
            setup_data = []

            for i, bank_name in enumerate(banks):
                # For each bank, gather its accounts
                account_types  = request.form.getlist(f"account_type_{i}[]")
                account_balances = request.form.getlist(f"account_balance_{i}[]")
                # In your form, you might also have account_name_i[] if you store the account "nickname".
                # But if you only track type & balance, you can skip the name field.

                # Combine into a list of dicts
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

            # 2. Build the final_matrix for the desired layout
            #    Columns: Bank Name | Account Type | Current Balance
            final_matrix = []
            final_matrix.append(["Bank Name", "Account Type", "Current Balance"])

            grand_total = 0.0

            # For each bank in setup_data
            for bank_info in setup_data:
                bank_name = bank_info["bank"]
                bank_accounts = bank_info["accounts"]
                bank_total = 0.0
                first_row = True

                # Add each account in a separate row
                for acc in bank_accounts:
                    row = []
                    if first_row:
                        row.append(bank_name)  # "Bank Name" column
                        first_row = False
                    else:
                        row.append("")         # leave blank under the same bank

                    row.append(acc["type"])   # "Account Type" column
                    balance_val = float(acc["balance"] or 0.0)
                    row.append(balance_val)    # "Current Balance" column

                    bank_total += balance_val
                    final_matrix.append(row)

                # Add a "Total (BankName)" row
                final_matrix.append([f"Total ({bank_name})", "", bank_total])
                grand_total += bank_total

            # Add the final "Grand Total (All Banks)" row
            final_matrix.append([f"Grand Total (All Banks)", "", grand_total])

            # 3. Update or create the "banking information" worksheet
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
#  Run Flask (demo)
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
