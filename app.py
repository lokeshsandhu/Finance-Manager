from flask import Flask, request, jsonify, render_template
import os, json, datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Google Sheets Setup
scope = [
    "https://spreadsheets.google.com/feeds", 
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file", 
    "https://www.googleapis.com/auth/drive"
]
creds_json = os.getenv("GOOGLE_CREDENTIALS")
if not creds_json:
    raise Exception("GOOGLE_CREDENTIALS not set")
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)
client = gspread.authorize(creds)

# Open main transaction sheet
try:
    sheet = client.open("Finance Manager").sheet1  
except Exception as e:
    raise Exception("Main transaction sheet not found. Ensure a sheet named 'Finance Manager' exists.") from e

@app.route("/")
def home():
    try:
        # Load banks and accounts from the "banking information" worksheet.
        try:
            bank_sheet = client.open("Finance Manager").worksheet("banking information")
            bank_headers = bank_sheet.row_values(1)  # First row: "Bank", BMO, RBC, etc.
            banks_data = {}
            # For each bank column (skip the first header cell), get account names from rows 3 to 5.
            for col_index, bank in enumerate(bank_headers[1:], start=1):
                if bank:
                    data = bank_sheet.col_values(col_index + 1)  # Get entire column (1-indexed)
                    # Assume account names are in rows 3-5 (if available)
                    accounts = data[2:5]
                    banks_data[bank] = accounts
            return render_template("index.html", default_date=datetime.date.today().isoformat(), banks=banks_data)
        except gspread.exceptions.WorksheetNotFound:
            # No setup data yet; pass an empty dictionary.
            return render_template("index.html", default_date=datetime.date.today().isoformat(), banks={})
    except Exception as e:
        return render_template("index.html", default_date=datetime.date.today().isoformat(), banks={}, error=str(e))

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    try:
        data = request.form
        # Determine direction: if "Outgoing", amount is negative; if "Incoming", positive.
        direction = data.get("transaction_direction", "Outgoing")
        amount = float(data["amount"])
        if direction == "Outgoing":
            amount = -abs(amount)
        else:
            amount = abs(amount)
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

@app.route("/view_transactions")
def view_transactions():
    try:
        transactions = sheet.get_all_records()
        formatted_transactions = []
        # Expected headers: Date, Time, Type, Bank, Account, Direction, Amount, Purpose
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

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if request.method == "GET":
        return render_template("setup.html", banks={})
    else:
        try:
            banks = request.form.getlist("bank[]")
            setup_data = []
            for i, bank in enumerate(banks):
                account_names = request.form.getlist(f"account_name_{i}[]")
                account_types = request.form.getlist(f"account_type_{i}[]")
                account_balances = request.form.getlist(f"account_balance_{i}[]")
                accounts = []
                for name, a_type, balance in zip(account_names, account_types, account_balances):
                    accounts.append({
                        "name": name,
                        "type": a_type,
                        "balance": balance
                    })
                setup_data.append({"bank": bank, "accounts": accounts})
            # Format the "banking information" worksheet as desired.
            # Format:
            # Row1: ["Bank", bank1, bank2, ...]
            # Row2: ["Balance", "", "", ...]
            # Row3: ["Checking", <bank1 Checking>, <bank2 Checking>, ...]
            # Row4: ["Savings", <bank1 Savings>, <bank2 Savings>, ...]
            # Row5: ["Credit Card", <bank1 Credit Card>, <bank2 Credit Card>, ...]
            # Row6: ["Bank Totals", total1, total2, ...]
            # Row7: ["Total", overall total, "", ...]
            account_order = ["Checking", "Savings", "Credit Card", "Investment"]
            banks_list = [d["bank"] for d in setup_data]
            header_row = ["Bank"] + banks_list
            balance_row = ["Balance"] + ["" for _ in banks_list]
            account_rows = []
            for acc_type in account_order:
                row = [acc_type]
                for d in setup_data:
                    val = ""
                    for account in d["accounts"]:
                        if account["type"] == acc_type:
                            val = account["name"] + " $" + str(account["balance"])
                            break
                    row.append(val)
                account_rows.append(row)
            totals_row = ["Bank Totals"]
            for d in setup_data:
                total = 0
                for account in d["accounts"]:
                    try:
                        total += float(account["balance"])
                    except:
                        pass
                totals_row.append(total)
            overall_total = sum(totals_row[1:])
            total_row = ["Total", overall_total] + ["" for _ in range(len(banks_list)-1)]
            final_matrix = [header_row, balance_row] + account_rows + [totals_row, total_row]

            try:
                bank_sheet = client.open("Finance Manager").worksheet("banking information")
                bank_sheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                bank_sheet = client.open("Finance Manager").add_worksheet(title="banking information", rows="100", cols="20")
            bank_sheet.update("A1", final_matrix)
            return jsonify({"message": "Setup preferences saved successfully!", "data": setup_data}), 200
        except Exception as e:
            return jsonify({"message": "Error saving setup preferences", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
