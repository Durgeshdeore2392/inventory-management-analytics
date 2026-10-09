import pytest
import os
import sqlite3
import pandas as pd
from src.database import init_db, fetch_products, fetch_transactions
from src.inventory import (
    validate_product_data,
    create_product,
    edit_product,
    remove_product,
    process_transaction,
    classify_stock_level
)

@pytest.fixture
def temp_db(tmp_path):
    """Creates a temporary test database file."""
    db_file = os.path.join(tmp_path, "test_inventory.db")
    init_db(db_path=db_file, seed_sample_data=False)
    return db_file

def test_validate_product_data():
    # Valid product
    is_valid, errors = validate_product_data(
        "TEST-001", "Test Product", "Electronics", "Test Supplier",
        25.0, 50.0, 100, 20, 50, 7
    )
    assert is_valid is True
    assert len(errors) == 0

    # Invalid SKU & negative cost
    is_valid, errors = validate_product_data(
        "T", "", "Electronics", "Test Supplier",
        -10.0, 50.0, -5, 20, 0, -1
    )
    assert is_valid is False
    assert len(errors) >= 4

def test_create_and_fetch_product(temp_db):
    success, prod_id, msg = create_product(
        "TEST-SKU1", "Widget A", "Electronics", "Acme Corp",
        15.0, 30.0, 50, 10, 25, 5, db_path=temp_db
    )
    assert success is True
    assert prod_id is not None

    df = fetch_products(db_path=temp_db)
    assert len(df) == 1
    assert df.iloc[0]["sku"] == "TEST-SKU1"
    assert df.iloc[0]["current_stock"] == 50

def test_edit_product(temp_db):
    _, prod_id, _ = create_product(
        "TEST-SKU2", "Widget B", "Apparel & Gear", "Apex Supplies",
        20.0, 40.0, 30, 15, 50, 10, db_path=temp_db
    )
    
    success, msg = edit_product(
        prod_id, "TEST-SKU2-UPD", "Widget B Updated", "Apparel & Gear", "Apex Supplies",
        22.0, 45.0, 40, 20, 60, 12, db_path=temp_db
    )
    assert success is True

    df = fetch_products(db_path=temp_db)
    assert df.iloc[0]["sku"] == "TEST-SKU2-UPD"
    assert df.iloc[0]["product_name"] == "Widget B Updated"
    assert df.iloc[0]["unit_cost"] == 22.0

def test_remove_product(temp_db):
    _, prod_id, _ = create_product(
        "TEST-SKU3", "Widget C", "Office Supplies", "Office Depot",
        5.0, 10.0, 100, 20, 50, 3, db_path=temp_db
    )
    
    success, msg = remove_product(prod_id, db_path=temp_db)
    assert success is True

    df = fetch_products(db_path=temp_db)
    assert len(df) == 0

def test_stock_transaction_purchase_and_sale(temp_db):
    _, prod_id, _ = create_product(
        "TEST-SKU4", "Widget D", "Home & Kitchen", "Kitchen Inc",
        10.0, 20.0, 20, 5, 25, 7, db_path=temp_db
    )

    # Process Purchase -> Stock increases from 20 to 50
    success, msg = process_transaction(
        prod_id, "Purchase", 30, 10.0, notes="Restock", db_path=temp_db
    )
    assert success is True
    df_p = fetch_products(db_path=temp_db)
    assert df_p.iloc[0]["current_stock"] == 50

    # Process Sale -> Stock decreases from 50 to 35
    success, msg = process_transaction(
        prod_id, "Sale", 15, 20.0, notes="Customer Purchase", db_path=temp_db
    )
    assert success is True
    df_s = fetch_products(db_path=temp_db)
    assert df_s.iloc[0]["current_stock"] == 35

    # Check transactions log table
    tx_df = fetch_transactions(product_id=prod_id, db_path=temp_db)
    assert len(tx_df) == 2

def test_prevent_negative_stock(temp_db):
    _, prod_id, _ = create_product(
        "TEST-SKU5", "Widget E", "Electronics", "Tech Co",
        50.0, 100.0, 10, 5, 20, 5, db_path=temp_db
    )

    # Attempt to sell 15 when only 10 in stock
    success, msg = process_transaction(
        prod_id, "Sale", 15, 100.0, db_path=temp_db
    )
    assert success is False
    assert "Insufficient stock" in msg

    # Verify stock remains unchanged at 10
    df = fetch_products(db_path=temp_db)
    assert df.iloc[0]["current_stock"] == 10

def test_classify_stock_level():
    assert classify_stock_level(0, 10) == "Out of Stock"
    assert classify_stock_level(5, 10) == "Low Stock"
    assert classify_stock_level(10, 10) == "Low Stock"
    assert classify_stock_level(20, 10) == "Optimal"
    assert classify_stock_level(50, 10) == "Excess Stock"
