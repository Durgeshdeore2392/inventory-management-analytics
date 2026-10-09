import re
import pandas as pd
from .database import (
    add_product,
    update_product,
    delete_product,
    record_transaction,
    fetch_products
)

def validate_product_data(sku, product_name, category, supplier, unit_cost, selling_price, current_stock, reorder_point, min_order_qty, supplier_lead_time_days):
    """
    Validates input parameters for product creation and updating.
    Returns (is_valid, list_of_error_messages).
    """
    errors = []

    if not sku or not isinstance(sku, str) or len(sku.strip()) < 3:
        errors.append("SKU must be at least 3 characters long.")

    if not product_name or not isinstance(product_name, str) or len(product_name.strip()) < 2:
        errors.append("Product name must be at least 2 characters long.")

    if not category or not isinstance(category, str):
        errors.append("Category is required.")

    if not supplier or not isinstance(supplier, str):
        errors.append("Supplier is required.")

    try:
        cost = float(unit_cost)
        if cost < 0:
            errors.append("Unit cost cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Unit cost must be a valid number.")

    try:
        price = float(selling_price)
        if price < 0:
            errors.append("Selling price cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Selling price must be a valid number.")

    try:
        stock = int(current_stock)
        if stock < 0:
            errors.append("Stock quantity cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Current stock must be a valid integer.")

    try:
        rop = int(reorder_point)
        if rop < 0:
            errors.append("Reorder point cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Reorder point must be a valid integer.")

    try:
        moq = int(min_order_qty)
        if moq <= 0:
            errors.append("Minimum order quantity must be greater than zero.")
    except (ValueError, TypeError):
        errors.append("Minimum order quantity must be a valid integer.")

    try:
        lt = int(supplier_lead_time_days)
        if lt < 0:
            errors.append("Supplier lead time cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Supplier lead time must be a valid integer.")

    return len(errors) == 0, errors

def classify_stock_level(current_stock, reorder_point):
    """
    Classifies inventory status based on current stock vs reorder point.
    """
    if current_stock == 0:
        return "Out of Stock"
    elif current_stock <= reorder_point:
        return "Low Stock"
    elif current_stock > reorder_point * 3.5:
        return "Excess Stock"
    else:
        return "Optimal"

def create_product(sku, product_name, category, supplier, unit_cost, selling_price, current_stock, reorder_point, min_order_qty, supplier_lead_time_days, db_path=None):
    """Validates and creates a new product in inventory."""
    is_valid, errors = validate_product_data(
        sku, product_name, category, supplier, unit_cost, selling_price, current_stock, reorder_point, min_order_qty, supplier_lead_time_days
    )
    if not is_valid:
        return False, None, " | ".join(errors)

    return add_product(
        sku.strip().upper(), product_name.strip(), category.strip(), supplier.strip(),
        float(unit_cost), float(selling_price), int(current_stock),
        int(reorder_point), int(min_order_qty), int(supplier_lead_time_days), db_path=db_path
    )

def edit_product(product_id, sku, product_name, category, supplier, unit_cost, selling_price, current_stock, reorder_point, min_order_qty, supplier_lead_time_days, db_path=None):
    """Validates and updates an existing product in inventory."""
    is_valid, errors = validate_product_data(
        sku, product_name, category, supplier, unit_cost, selling_price, current_stock, reorder_point, min_order_qty, supplier_lead_time_days
    )
    if not is_valid:
        return False, " | ".join(errors)

    return update_product(
        product_id, sku.strip().upper(), product_name.strip(), category.strip(), supplier.strip(),
        float(unit_cost), float(selling_price), int(current_stock),
        int(reorder_point), int(min_order_qty), int(supplier_lead_time_days), db_path=db_path
    )

def remove_product(product_id, db_path=None):
    """Deletes a product by ID."""
    return delete_product(product_id, db_path=db_path)

def process_transaction(product_id, transaction_type, quantity, unit_price, transaction_date=None, notes="", allow_negative_stock=False, db_path=None):
    """High-level transaction processing wrapper."""
    return record_transaction(
        product_id=product_id,
        transaction_type=transaction_type,
        quantity=int(quantity),
        unit_price=float(unit_price),
        transaction_date=transaction_date,
        notes=notes,
        allow_negative_stock=allow_negative_stock,
        db_path=db_path
    )

def filter_products(df, category=None, stock_status=None, search_term=None):
    """Applies multiple filters to a product DataFrame."""
    filtered_df = df.copy()

    if category and category != "All":
        filtered_df = filtered_df[filtered_df["category"] == category]

    if stock_status and stock_status != "All":
        status_series = filtered_df.apply(
            lambda r: classify_stock_level(r["current_stock"], r["reorder_point"]), axis=1
        )
        filtered_df = filtered_df[status_series == stock_status]

    if search_term:
        term = search_term.lower()
        mask = (
            filtered_df["sku"].str.lower().str.contains(term, na=False) |
            filtered_df["product_name"].str.lower().str.contains(term, na=False) |
            filtered_df["supplier"].str.lower().str.contains(term, na=False)
        )
        filtered_df = filtered_df[mask]

    return filtered_df
