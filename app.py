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
sheet = client.open("Finance Manager").sheet1  # Ensure your sheet's header row matches the keys below

# Helper: Adjust for header row
def get_sheet_row(transaction_id):
    return transaction_id + 1  # header is assumed to be row 1

@app.route("/")
def home():
    # Pass today's date to set the default value for date fields
    today = datetime.date.today().isoformat()
    return render_template("index.html", default_date=today)

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    try:
        data = request.form
        # Append transaction: Date, Type, Bank, Account, Amount, Purpose, Place, Refund Status
        sheet.append_row([
            data["date"], 
            data["type"], 
            data["bank"], 
            data["account"], 
            data["amount"], 
            data["purpose"], 
            data["place"],
            ""  # Initially, no refund status
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
            data["type"],
            data["bank"],
            data["account"],
            data["amount"],
            data["purpose"],
            data["place"],
            data.get("refund_status", "")  # Preserve refund status if present
        ]
        row_number = get_sheet_row(transaction_id)
        sheet.update(f"A{row_number}:H{row_number}", [updated_row])
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
        refund_type = request.form.get("refund_type", "full")  # full or partial
        refund_amount = request.form.get("refund_amount", "")
        row_number = get_sheet_row(transaction_id)
        # Mark the transaction as refunded in the "Refund Status" column
        refund_status = f"Refunded ({refund_type})"
        if refund_type == "partial" and refund_amount:
            refund_status += f" - ${refund_amount}"
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
            # Combine all transaction values to search for the keyword
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
        # Render the setup page that allows bank and account entry.
        return render_template("setup.html")
    else:
        try:
            bank = request.form.get("bank")
            # Use getlist to receive multiple account entries.
            account_names = request.form.getlist("account_name[]")
            account_balances = request.form.getlist("account_balance[]")
            
            # For demonstration, we'll simply log the received values.
            print("Setup Bank:", bank)
            for name, balance in zip(account_names, account_balances):
                print(f"Account: {name}, Balance: {balance}")
            
            # In a real app, you might save this configuration to a database or another Google Sheet.
            return jsonify({"message": "Setup preferences saved!"}), 200
        except Exception as e:
            return jsonify({"message": "Error saving setup preferences", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
