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
# Main transaction sheet
sheet = client.open("Finance Manager").sheet1  # Ensure its header row matches below

# Helper: Adjust for header row (assumes header is row 1)
def get_sheet_row(transaction_id):
    return transaction_id + 1

# ------------------ Main Page Routes ------------------

@app.route("/")
def home():
    today = datetime.date.today().isoformat()
    return render_template("index.html", default_date=today)

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    try:
        data = request.form
        # For interac across accounts, the bank and account fields may be combined already.
        date = data["date"]
        time_field = data["time"]
        type_field = data["type"]
        bank = data.get("bank", "")
        account = data.get("account", "")
        amount = data["amount"]
        purpose = data["purpose"]
        balance_left = data.get("balance_left", "")
        # Append a new row to the main sheet.
        # Columns: Date, Time, Type, Bank, Account, Amount, Purpose, Balance Left, Refund Status
        sheet.append_row([date, time_field, type_field, bank, account, amount, purpose, balance_left, ""])
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
                "time": t.get("Time", ""),
                "type": t.get("Type", ""),
                "bank": t.get("Bank", ""),
                "account": t.get("Account", ""),
                "amount": t.get("Amount", ""),
                "purpose": t.get("Purpose", ""),
                "balance_left": t.get("Balance Left", ""),
                "refund_status": t.get("Refund Status", "")
            })
        return jsonify({"transactions": formatted_transactions}), 200
    except Exception as e:
        return jsonify({"message": "Error fetching transactions", "error": str(e)}), 500

@app.route("/edit_transaction", methods=["POST"])
def edit_transaction():
    try:
        transaction_id = int(request.form["id"])
        data = request.form
        updated_row = [
            data["date"],
            data["time"],
            data["type"],
            data["bank"],
            data["account"],
            data["amount"],
            data["purpose"],
            data.get("balance_left", ""),
            data.get("refund_status", "")
        ]
        row_number = get_sheet_row(transaction_id)
        sheet.update(f"A{row_number}:I{row_number}", [updated_row])
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
        refund_type = request.form.get("refund_type", "full")
        refund_amount = request.form.get("refund_amount", "")
        row_number = get_sheet_row(transaction_id)
        refund_status = f"Refunded ({refund_type})"
        if refund_type == "partial" and refund_amount:
            refund_status += f" - ${refund_amount}"
        sheet.update_cell(row_number, 9, refund_status)
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
                "time": t.get("Time", ""),
                "type": t.get("Type", ""),
                "bank": t.get("Bank", ""),
                "account": t.get("Account", ""),
                "amount": t.get("Amount", ""),
                "purpose": t.get("Purpose", ""),
                "balance_left": t.get("Balance Left", ""),
                "refund_status": t.get("Refund Status", "")
            })
        return jsonify({"transactions": filtered}), 200
    except Exception as e:
        return jsonify({"message": "Error searching transactions", "error": str(e)}), 500

# ------------------ Setup Routes ------------------
@app.route("/setup", methods=["GET", "POST"])
def setup():
    if request.method == "GET":
        return render_template("setup.html")
    else:
        try:
            # Gather multiple bank blocks.
            banks = request.form.getlist("bank[]")
            setup_data = []
            for i, bank in enumerate(banks):
                account_names = request.form.getlist(f"account_name_{i}[]")
                account_balances = request.form.getlist(f"account_balance_{i}[]")
                accounts = []
                total = 0
                for name, balance in zip(account_names, account_balances):
                    amt = float(balance)
                    accounts.append({"name": name, "balance": amt})
                    total += amt
                setup_data.append({"bank": bank, "accounts": accounts, "total": total})
            # Write setup_data to a worksheet named "banking information"
            try:
                bank_sheet = client.open("Finance Manager").worksheet("banking information")
                bank_sheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                bank_sheet = client.open("Finance Manager").add_worksheet(title="banking information", rows="100", cols="20")
            # Prepare data matrix.
            num_banks = len(setup_data)
            # First row: bank names.
            header = [d["bank"] for d in setup_data]
            data_matrix = [header]
            # Determine max number of accounts across banks.
            max_accounts = max(len(d["accounts"]) for d in setup_data) if setup_data else 0
            # For each account index, add two rows: one for account names, one for balances.
            for j in range(max_accounts):
                row_names = []
                row_balances = []
                for d in setup_data:
                    if j < len(d["accounts"]):
                        row_names.append(d["accounts"][j]["name"])
                        row_balances.append(d["accounts"][j]["balance"])
                    else:
                        row_names.append("")
                        row_balances.append("")
                data_matrix.append(row_names)
                data_matrix.append(row_balances)
            # Totals row per bank.
            totals = [d["total"] for d in setup_data]
            data_matrix.append(totals)
            # Overall total (you can adjust placement as desired)
            overall_total = sum(totals)
            overall_row = [overall_total] + [""]*(num_banks-1)
            data_matrix.append(overall_row)
            # Update the worksheet starting at A1.
            bank_sheet.update("A1", data_matrix)
            return jsonify({"message": "Setup preferences saved!", "data": setup_data}), 200
        except Exception as e:
            return jsonify({"message": "Error saving setup preferences", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
