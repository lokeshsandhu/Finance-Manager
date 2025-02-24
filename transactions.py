from flask import Blueprint, render_template, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os, json, datetime

transactions_bp = Blueprint('transactions', __name__)

# Google Sheets Setup (shared by both modules)
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

@transactions_bp.route("/")
def home():
    try:
        # Load bank/account data from the "banking information" worksheet.
        try:
            bank_sheet = client.open("Finance Manager").worksheet("banking information")
            # Assume the sheet header row is like: ["Bank Name", "BMO", "RBC", "CIBC", "Cash"]
            bank_headers = bank_sheet.row_values(1)
            banks_data = {}
            # For each bank column (skip the first cell), get account names from rows 3 to 5.
            for col_index, bank in enumerate(bank_headers[1:], start=1):
                if bank:
                    col_values = bank_sheet.col_values(col_index+1)
                    # Assume account names are in rows 3-5; remove empty cells.
                    accounts = [a for a in col_values[2:5] if a]
                    banks_data[bank] = accounts
            return render_template("index.html", 
                                   default_date=datetime.date.today().isoformat(), 
                                   banks=banks_data)
        except gspread.exceptions.WorksheetNotFound:
            return render_template("index.html", 
                                   default_date=datetime.date.today().isoformat(), 
                                   banks={})
    except Exception as e:
        return render_template("index.html", 
                               default_date=datetime.date.today().isoformat(), 
                               banks={}, error=str(e))

@transactions_bp.route("/add_transaction", methods=["POST"])
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
        # Expected columns: Date, Time, Type, Bank, Account, Direction, Amount, Purpose
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

@transactions_bp.route("/view_transactions")
def view_transactions():
    try:
        transactions = sheet.get_all_records()
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
                "purpose": t.get("Purpose", "")
            })
        return jsonify({"transactions": formatted_transactions}), 200
    except Exception as e:
        return jsonify({"message": "Error fetching transactions", "error": str(e)}), 500

@transactions_bp.route("/search_transactions")
def search_transactions():
    try:
        keyword = request.args.get("keyword", "").lower()
        transactions = sheet.get_all_records()
        filtered = []
        for t in transactions:
            combined = " ".join(str(v) for v in t.values()).lower()
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
