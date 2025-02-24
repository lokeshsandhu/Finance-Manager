from flask import Flask, render_template, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import os

app = Flask(__name__)

# Setup Google Sheets credentials from environment variable
def get_credentials():
    """Get credentials from environment variable"""
    try:
        creds_dict = json.loads(os.environ.get('GOOGLE_CREDENTIALS', '{}'))
        return ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict,
            ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        )
    except Exception as e:
        print(f"Error loading credentials: {str(e)}")
        return None

# Initialize Google Sheets client
def init_sheets_client():
    """Initialize and return Google Sheets client"""
    try:
        creds = get_credentials()
        if not creds:
            raise Exception("Failed to load credentials")
        return gspread.authorize(creds)
    except Exception as e:
        print(f"Error initializing sheets client: {str(e)}")
        return None

# Initialize client and worksheets
client = init_sheets_client()
if client:
    try:
        workbook = client.open("Finance Manager")
        sheet = workbook.sheet1
        setup_sheet = workbook.worksheet("Setup")
    except Exception as e:
        print(f"Error opening sheets: {str(e)}")
        sheet = None
        setup_sheet = None

def get_banks_data():
    """Fetch banks and accounts data from setup sheet"""
    try:
        setup_data = setup_sheet.get_all_records()
        banks = {}
        for row in setup_data:
            if row['Bank'] and row['Account']:
                if row['Bank'] not in banks:
                    banks[row['Bank']] = []
                banks[row['Bank']].append({
                    'name': row['Account'],
                    'type': row['Type'],
                    'balance': float(row['Balance'] if row['Balance'] else 0)
                })
        return banks
    except Exception as e:
        print(f"Error fetching banks data: {str(e)}")
        return {}

@app.route('/')
def index():
    banks = get_banks_data()
    default_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('index.html', banks=banks, default_date=default_date)

@app.route('/setup')
def setup():
    banks = get_banks_data()
    return render_template('setup.html', banks=banks)

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    try:
        data = request.form
        
        # Format amount based on direction
        amount = float(data['amount'])
        if data['transaction_direction'] == 'Outgoing':
            amount = -amount
            
        # Prepare row data
        row_data = [
            data['date'],
            data['time'],
            data['type'],
            data['bank'],
            data['account'],
            data['transaction_direction'],
            amount,
            data['purpose']
        ]
        
        # Add to transactions sheet
        sheet.append_row(row_data)
        
        # Update bank balance if not cash
        if data['bank'] != 'Cash':
            update_bank_balance(data['bank'], data['account'], amount)
            
        # Handle Interac transfers
        if data['type'] == 'Interac' and data.get('interac_type') == 'Across Accounts':
            # Create opposite transaction for target account
            target_amount = -amount
            target_direction = 'Incoming' if data['transaction_direction'] == 'Outgoing' else 'Outgoing'
            
            target_row = [
                data['date'],
                data['time'],
                'Interac',
                data['target_bank'],
                data['target_account'],
                target_direction,
                target_amount,
                f"Interac transfer {data['purpose']}"
            ]
            
            sheet.append_row(target_row)
            update_bank_balance(data['target_bank'], data['target_account'], target_amount)
            
        return jsonify({"message": "Transaction added successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Error adding transaction: {str(e)}"}), 500

@app.route('/edit_transaction', methods=['POST'])
def edit_transaction():
    try:
        data = request.form
        row_index = int(data['row_index'])
        
        # Get original transaction data
        original_transaction = sheet.row_values(row_index)
        original_amount = float(original_transaction[6])
        
        # Calculate new amount
        new_amount = float(data['amount'])
        if data['transaction_direction'] == 'Outgoing':
            new_amount = -new_amount
            
        # Calculate balance adjustment
        balance_adjustment = new_amount - original_amount
        
        # Update transaction
        sheet.update(f'A{row_index}:H{row_index}', [[
            data['date'],
            data['time'],
            data['type'],
            data['bank'],
            data['account'],
            data['transaction_direction'],
            new_amount,
            data['purpose']
        ]])
        
        # Update bank balance if not cash
        if data['bank'] != 'Cash':
            update_bank_balance(data['bank'], data['account'], balance_adjustment)
            
        return jsonify({"message": "Transaction updated successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Error updating transaction: {str(e)}"}), 500

@app.route('/delete_transaction', methods=['POST'])
def delete_transaction():
    try:
        row_index = int(request.form['row_index'])
        
        # Get transaction data before deletion
        transaction = sheet.row_values(row_index)
        amount = float(transaction[6])
        bank = transaction[3]
        account = transaction[4]
        
        # Delete the row
        sheet.delete_rows(row_index)
        
        # Update bank balance if not cash
        if bank != 'Cash':
            update_bank_balance(bank, account, -amount)  # Reverse the amount
            
        return jsonify({"message": "Transaction deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Error deleting transaction: {str(e)}"}), 500

@app.route('/refund_transaction', methods=['POST'])
def refund_transaction():
    try:
        data = request.form
        row_index = int(data['row_index'])
        refund_amount = float(data['refund_amount'])
        
        # Get original transaction
        original_transaction = sheet.row_values(row_index)
        
        # Create refund transaction
        refund_data = [
            datetime.now().strftime('%Y-%m-%d'),
            datetime.now().strftime('%H:%M'),
            'Refund',
            original_transaction[3],  # Bank
            original_transaction[4],  # Account
            'Incoming',
            refund_amount,
            f"Refund for transaction #{row_index}"
        ]
        
        # Add refund transaction
        sheet.append_row(refund_data)
        
        # Update original transaction with refund note
        current_purpose = original_transaction[7]
        sheet.update_cell(row_index, 8, f"{current_purpose} (Refunded: ${refund_amount})")
        
        # Update bank balance if not cash
        if original_transaction[3] != 'Cash':
            update_bank_balance(original_transaction[3], original_transaction[4], refund_amount)
            
        return jsonify({"message": "Refund processed successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Error processing refund: {str(e)}"}), 500

@app.route('/view_transactions')
def view_transactions():
    try:
        # Get filter parameters
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        keyword = request.args.get('keyword', '').lower()
        bank = request.args.get('bank')
        account = request.args.get('account')
        transaction_type = request.args.get('type')
        amount_min = request.args.get('amount_min')
        amount_max = request.args.get('amount_max')
        direction = request.args.get('direction')
        
        # Get all transactions
        transactions = sheet.get_all_records()
        
        # Apply filters
        filtered_transactions = []
        for transaction in transactions:
            # Date filter
            if date_start and transaction['Date'] < date_start:
                continue
            if date_end and transaction['Date'] > date_end:
                continue
                
            # Keyword filter
            if keyword and keyword not in str(transaction).lower():
                continue
                
            # Bank filter
            if bank and transaction['Bank'] != bank:
                continue
                
            # Account filter
            if account and transaction['Account'] != account:
                continue
                
            # Type filter
            if transaction_type and transaction['Type'] != transaction_type:
                continue
                
            # Amount filter
            amount = float(transaction['Amount'])
            if amount_min and amount < float(amount_min):
                continue
            if amount_max and amount > float(amount_max):
                continue
                
            # Direction filter
            if direction and transaction['Direction'] != direction:
                continue
                
            filtered_transactions.append(transaction)
            
        return jsonify({"transactions": filtered_transactions}), 200
    except Exception as e:
        return jsonify({"message": f"Error fetching transactions: {str(e)}"}), 500

@app.route('/setup', methods=['POST'])
def save_setup():
    try:
        data = request.form
        
        # Clear existing setup data
        setup_sheet.clear()
        
        # Add headers
        setup_sheet.append_row(['Bank', 'Account', 'Type', 'Balance'])
        
        # Process each bank and its accounts
        banks = data.getlist('bank[]')
        for i, bank in enumerate(banks):
            account_names = data.getlist(f'account_name_{i}[]')
            account_types = data.getlist(f'account_type_{i}[]')
            account_balances = data.getlist(f'account_balance_{i}[]')
            
            for name, type_, balance in zip(account_names, account_types, account_balances):
                setup_sheet.append_row([bank, name, type_, float(balance)])
                
        return jsonify({"message": "Setup saved successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Error saving setup: {str(e)}"}), 500

def update_bank_balance(bank, account, amount_change):
    """Helper function to update bank balance in setup sheet"""
    try:
        setup_data = setup_sheet.get_all_records()
        for i, row in enumerate(setup_data, start=2):  # start=2 to account for header row
            if row['Bank'] == bank and row['Account'] == account:
                current_balance = float(row['Balance'])
                new_balance = current_balance + amount_change
                setup_sheet.update_cell(i, 4, new_balance)  # 4 is the Balance column
                break
    except Exception as e:
        print(f"Error updating bank balance: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True)
