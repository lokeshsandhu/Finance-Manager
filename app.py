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
                    if col_index < len(row) and row[col_index]:  # Only add if an account exists
                        # Include account name and balance as a dictionary
                        banks_data[bank].append({
                            "name": row[col_index],
                            "balance": row[col_index + len(bank_headers)] if col_index + len(bank_headers) < len(row) else "0"
                        })

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
        
        # Handle bank and account information
        bank = data.get("bank", "")
        account = data.get("account", "")
        
        # For Cash transactions, set bank and account to "Cash"
        if data["type"] == "Cash":
            bank = "Cash"
            account = "Cash"
        
        # Update balance if bank and account are provided
        balance_left = ""
        if bank and account and bank != "Cash":
            try:
                bank_sheet = client.open("Finance Manager").worksheet("banking information")
                bank_headers = bank_sheet.row_values(1)
                
                # Find bank column index
                bank_col = bank_headers.index(bank) if bank in bank_headers else -1
                
                if bank_col >= 0:
                    # Find account row
                    accounts_col = bank_sheet.col_values(bank_col + 1)
                    account_row = -1
                    for i, acc in enumerate(accounts_col):
                        if acc == account:
                            account_row = i + 1  # +1 because sheet rows are 1-indexed
                            break
                    
                    if account_row > 0:
                        # Get balance column index (columns after all banks are balances)
                        balance_col = len(bank_headers) + bank_col + 1
                        
                        # Get current balance
                        current_balance = float(bank_sheet.cell(account_row, balance_col).value or 0)
                        
                        # Update balance based on transaction type
                        if transaction_type == "Outgoing":
                            new_balance = current_balance - amount
                        else:  # Incoming
                            new_balance = current_balance + amount
                        
                        # Update balance in sheet
                        bank_sheet.update_cell(account_row, balance_col, new_balance)
                        balance_left = str(new_balance)
            except Exception as e:
                print(f"Error updating balance: {str(e)}")
        
        # Set amount sign based on direction
        signed_amount = -amount if transaction_type == "Outgoing" else amount

        # Update transaction sheet
        sheet.append_row([
            data["date"], data["time"], data["type"], 
            bank, account, 
            transaction_type, signed_amount, data["purpose"], balance_left, 
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Add timestamp
        ])
        
        return jsonify({"message": "Transaction Added Successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error adding transaction", "error": str(e)}), 500

@app.route("/view_transactions")
def view_transactions():
    try:
        # Get date filter if provided
        date_filter = request.args.get("date", "")
        
        # Get all transactions
        transactions = sheet.get_all_records()
        
        # Filter by date if provided
        if date_filter:
            transactions = [t for t in transactions if t.get("Date") == date_filter]
        
        # Format transactions for display
        formatted_transactions = []
        for t in transactions:
            formatted_transactions.append({
                "Date": t.get("Date", ""),  
                "Time": t.get("Time", ""),  
                "Type": t.get("Type", ""),  
                "Bank": t.get("Bank", ""),  
                "Account": t.get("Account", ""),  
                "Direction": t.get("Direction", ""),  
                "Amount": t.get("Amount", ""),  
                "Purpose": t.get("Purpose", ""),  
            })
            
        return jsonify({"transactions": formatted_transactions}), 200
    except Exception as e:
        return jsonify({"message": "Error fetching transactions", "error": str(e)}), 500

@app.route("/search_transactions")
def search_transactions():
    try:
        keyword = request.args.get("keyword", "").lower()
        date_filter = request.args.get("date", "")
        bank_filter = request.args.get("bank", "")
        account_filter = request.args.get("account", "")
        
        transactions = sheet.get_all_records()
        filtered = []
        
        for t in transactions:
            match = True
            
            # Apply all filters
            if date_filter and t.get("Date") != date_filter:
                match = False
            if bank_filter and t.get("Bank") != bank_filter:
                match = False
            if account_filter and t.get("Account") != account_filter:
                match = False
            if keyword and not any(keyword in str(value).lower() for value in t.values()):
                match = False
                
            if match:
                filtered.append(t)
                
        return jsonify({"transactions": filtered}), 200
    except Exception as e:
        return jsonify({"message": "Error searching transactions", "error": str(e)}), 500

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if request.method == "GET":
        return render_template("setup.html")
    
    if request.method == "POST":
        try:
            # Get setup data
            banks = request.form.getlist("bank[]")
            
            # Create or access banking information sheet
            try:
                bank_sheet = client.open("Finance Manager").worksheet("banking information")
            except gspread.exceptions.WorksheetNotFound:
                bank_sheet = client.open("Finance Manager").add_worksheet(
                    title="banking information", rows=100, cols=100
                )
            
            # Clear current data
            bank_sheet.clear()
            
            # Add bank headers
            bank_sheet.append_row(banks)
            
            # Process accounts for each bank
            for i, bank in enumerate(banks):
                account_names = request.form.getlist(f"account_name_{i}[]")
                account_balances = request.form.getlist(f"account_balance_{i}[]")
                
                # Add each account in its respective column
                for j, account in enumerate(account_names):
                    # Add account to correct column
                    cell = bank_sheet.cell(j+2, i+1)  # +2 for row because 1-indexed and header row
                    cell.value = account
                    bank_sheet.update_cell(j+2, i+1, account)
                    
                    # Add balance in the corresponding balance column
                    # (after all bank columns)
                    balance_col = len(banks) + i + 1
                    bank_sheet.update_cell(j+2, balance_col, account_balances[j])
            
            return jsonify({"message": "Setup saved successfully!"}), 200
        except Exception as e:
            return jsonify({"message": "Error saving setup", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
