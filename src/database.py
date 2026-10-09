import sqlite3
import os
import pandas as pd
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "inventory.db")
PRODUCTS_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "products.csv")
TRANSACTIONS_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "transactions.csv")

def get_connection(db_path=None):
    """Establishes and returns a connection to the SQLite database."""
    target_path = db_path if db_path else DB_PATH
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=None, seed_sample_data=True):
    """Creates tables if they do not exist and populates initial sample data if requested and empty."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE NOT NULL,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        supplier TEXT NOT NULL,
        unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
        selling_price REAL NOT NULL CHECK(selling_price >= 0),
        current_stock INTEGER NOT NULL DEFAULT 0,
        reorder_point INTEGER NOT NULL DEFAULT 10 CHECK(reorder_point >= 0),
        min_order_qty INTEGER NOT NULL DEFAULT 50 CHECK(min_order_qty >= 0),
        supplier_lead_time_days INTEGER NOT NULL DEFAULT 7 CHECK(supplier_lead_time_days >= 0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        sku TEXT NOT NULL,
        transaction_type TEXT NOT NULL CHECK(transaction_type IN ('Sale', 'Purchase', 'Adjustment')),
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL CHECK(unit_price >= 0),
        total_amount REAL NOT NULL CHECK(total_amount >= 0),
        transaction_date TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
    );
    """)

    conn.commit()

    if seed_sample_data:
        # Seed initial data if products table is empty
        cursor.execute("SELECT COUNT(*) FROM products;")
        count = cursor.fetchone()[0]
        if count == 0:
            seed_from_csv(conn)

    conn.close()

def seed_from_csv(conn):
    """Seeds the SQLite database using synthetic products.csv and transactions.csv."""
    if os.path.exists(PRODUCTS_CSV_PATH):
        products_df = pd.read_csv(PRODUCTS_CSV_PATH)
        products_df.to_sql("products", conn, if_exists="append", index=False)
        conn.commit()

    if os.path.exists(TRANSACTIONS_CSV_PATH):
        tx_df = pd.read_csv(TRANSACTIONS_CSV_PATH)
        tx_df.to_sql("transactions", conn, if_exists="append", index=False)
        conn.commit()

def fetch_products(category=None, search_term=None, db_path=None):
    """Fetches all products with optional filtering by category and search term."""
    conn = get_connection(db_path)
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if category and category != "All":
        query += " AND category = ?"
        params.append(category)

    if search_term:
        query += " AND (product_name LIKE ? OR sku LIKE ? OR supplier LIKE ?)"
        term = f"%{search_term}%"
        params.extend([term, term, term])

    query += " ORDER BY product_id ASC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def fetch_transactions(product_id=None, transaction_type=None, start_date=None, end_date=None, db_path=None):
    """Fetches transactions with optional filtering criteria."""
    conn = get_connection(db_path)
    query = "SELECT t.*, p.product_name, p.category FROM transactions t LEFT JOIN products p ON t.product_id = p.product_id WHERE 1=1"
    params = []

    if product_id:
        query += " AND t.product_id = ?"
        params.append(product_id)

    if transaction_type and transaction_type != "All":
        query += " AND t.transaction_type = ?"
        params.append(transaction_type)

    if start_date:
        query += " AND t.transaction_date >= ?"
        params.append(str(start_date))

    if end_date:
        query += " AND t.transaction_date <= ?"
        params.append(str(end_date))

    query += " ORDER BY t.transaction_date DESC, t.transaction_id DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def add_product(sku, product_name, category, supplier, unit_cost, selling_price, current_stock, reorder_point, min_order_qty, supplier_lead_time_days, db_path=None):
    """Adds a new product to the database."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO products (sku, product_name, category, supplier, unit_cost, selling_price, current_stock, reorder_point, min_order_qty, supplier_lead_time_days)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sku, product_name, category, supplier, unit_cost, selling_price, current_stock, reorder_point, min_order_qty, supplier_lead_time_days))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return True, new_id, "Product added successfully!"
    except sqlite3.IntegrityError as e:
        conn.close()
        return False, None, f"Database Integrity Error: {str(e)}"
    except Exception as e:
        conn.close()
        return False, None, f"Error adding product: {str(e)}"

def update_product(product_id, sku, product_name, category, supplier, unit_cost, selling_price, current_stock, reorder_point, min_order_qty, supplier_lead_time_days, db_path=None):
    """Updates existing product specifications."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE products
            SET sku=?, product_name=?, category=?, supplier=?, unit_cost=?, selling_price=?, current_stock=?, reorder_point=?, min_order_qty=?, supplier_lead_time_days=?
            WHERE product_id=?
        """, (sku, product_name, category, supplier, unit_cost, selling_price, current_stock, reorder_point, min_order_qty, supplier_lead_time_days, product_id))
        conn.commit()
        conn.close()
        return True, "Product updated successfully!"
    except Exception as e:
        conn.close()
        return False, f"Error updating product: {str(e)}"

def delete_product(product_id, db_path=None):
    """Deletes a product and its associated transactions from the database."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM products WHERE product_id = ?", (product_id,))
        conn.commit()
        conn.close()
        return True, "Product deleted successfully!"
    except Exception as e:
        conn.close()
        return False, f"Error deleting product: {str(e)}"

def record_transaction(product_id, transaction_type, quantity, unit_price, transaction_date=None, notes="", allow_negative_stock=False, db_path=None):
    """
    Executes an inventory transaction atomically.
    Updates stock balance and inserts a transaction log record.
    """
    if quantity <= 0:
        return False, "Transaction quantity must be greater than zero."

    if not transaction_date:
        transaction_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT sku, current_stock FROM products WHERE product_id = ?", (product_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, f"Product ID {product_id} not found."

        sku = row["sku"]
        current_stock = row["current_stock"]

        # Calculate new stock level based on transaction type
        if transaction_type == "Sale":
            if not allow_negative_stock and current_stock < quantity:
                conn.close()
                return False, f"Insufficient stock! Available: {current_stock}, Requested: {quantity}."
            new_stock = current_stock - quantity
        elif transaction_type == "Purchase":
            new_stock = current_stock + quantity
        elif transaction_type == "Adjustment":
            # positive adjustment assumes adding to inventory, notes specify direction if negative
            new_stock = current_stock + quantity
        else:
            conn.close()
            return False, f"Invalid transaction type: {transaction_type}"

        if new_stock < 0 and not allow_negative_stock:
            conn.close()
            return False, "Transaction would result in negative stock level."

        # Execute stock update and log insertion inside transaction context
        total_amount = round(quantity * unit_price, 2)

        cursor.execute("UPDATE products SET current_stock = ? WHERE product_id = ?", (new_stock, product_id))
        cursor.execute("""
            INSERT INTO transactions (product_id, sku, transaction_type, quantity, unit_price, total_amount, transaction_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (product_id, sku, transaction_type, quantity, unit_price, total_amount, transaction_date, notes))

        conn.commit()
        conn.close()
        return True, f"Transaction recorded successfully! New stock level: {new_stock}."
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Database transaction failed: {str(e)}"
