"""
Data ingestion pipeline for ChatGraph AI.
Reads JSONL files, loads into SQLite, builds NetworkX graph.
"""

import json
import sqlite3
import os
import glob
import networkx as nx
import pickle

DATA_DIR = os.environ.get("DATA_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
DB_PATH = os.path.join(os.path.dirname(__file__), "o2c.db")
GRAPH_PATH = os.path.join(os.path.dirname(__file__), "graph.gpickle")


def read_jsonl_folder(folder_path: str) -> list[dict]:
    records = []
    for fpath in sorted(glob.glob(os.path.join(folder_path, "*.jsonl"))):
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


TABLES = [
    ("sales_order_headers", "sales_order_headers", ["salesOrder"]),
    ("sales_order_items", "sales_order_items", ["salesOrder", "salesOrderItem"]),
    ("sales_order_schedule_lines", "sales_order_schedule_lines", ["salesOrder", "salesOrderItem", "scheduleLine"]),
    ("outbound_delivery_headers", "outbound_delivery_headers", ["deliveryDocument"]),
    ("outbound_delivery_items", "outbound_delivery_items", ["deliveryDocument", "deliveryDocumentItem"]),
    ("billing_document_headers", "billing_document_headers", ["billingDocument"]),
    ("billing_document_items", "billing_document_items", ["billingDocument", "billingDocumentItem"]),
    ("journal_entry_items_accounts_receivable", "journal_entries", ["companyCode", "fiscalYear", "accountingDocument", "accountingDocumentItem"]),
    ("payments_accounts_receivable", "payments", ["companyCode", "fiscalYear", "accountingDocument", "accountingDocumentItem"]),
    ("business_partners", "business_partners", ["businessPartner"]),
    ("business_partner_addresses", "business_partner_addresses", ["businessPartner", "addressId"]),
    ("customer_company_assignments", "customer_company_assignments", ["customer", "companyCode"]),
    ("customer_sales_area_assignments", "customer_sales_area_assignments", ["customer", "salesOrganization", "distributionChannel", "division"]),
    ("products", "products", ["product"]),
    ("product_descriptions", "product_descriptions", ["product", "language"]),
    ("product_plants", "product_plants", ["product", "plant"]),
    ("product_storage_locations", "product_storage_locations", ["product", "plant", "storageLocation"]),
    ("plants", "plants", ["plant"]),
]

CANCELLATIONS_FOLDER = os.path.join("billing_document_headers", "billing_document_cancellations")


def sanitize_col(col: str) -> str:
    import re
    s = re.sub(r'([A-Z])', r'_\1', col).lower().lstrip('_')
    # handle consecutive uppercase like 'GLAccount' -> 'gl_account'
    s = re.sub(r'_([a-z])_([a-z])', lambda m: f"_{m.group(1)}{m.group(2)}", s)
    return s


def create_table_and_insert(conn: sqlite3.Connection, table_name: str, records: list[dict]):
    if not records:
        return

    # Get all unique keys across records
    all_keys = []
    seen = set()
    for r in records:
        for k in r.keys():
            if k not in seen:
                all_keys.append(k)
                seen.add(k)

    col_names = all_keys
    sql_cols = ", ".join(f'"{c}" TEXT' for c in col_names)
    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    conn.execute(f'CREATE TABLE "{table_name}" ({sql_cols})')

    placeholders = ", ".join(["?"] * len(col_names))
    insert_sql = f'INSERT INTO "{table_name}" ({", ".join(f"{c}" for c in col_names)}) VALUES ({placeholders})'

    rows = []
    for r in records:
        row = tuple(str(r.get(c, "")) if r.get(c) is not None else None for c in col_names)
        rows.append(row)

    conn.executemany(insert_sql, rows)
    conn.commit()
    print(f"  Inserted {len(rows)} rows into {table_name}")


def ingest_to_sqlite():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)

    for folder_name, table_name, _ in TABLES:
        folder_path = os.path.join(DATA_DIR, folder_name)
        if not os.path.isdir(folder_path):
            print(f"  Skipping {folder_name} - directory not found")
            continue
        print(f"Loading {folder_name}...")
        records = read_jsonl_folder(folder_path)
        create_table_and_insert(conn, table_name, records)

    # Cancellations subfolder
    cancel_path = os.path.join(DATA_DIR, CANCELLATIONS_FOLDER)
    if os.path.isdir(cancel_path):
        print("Loading billing_document_cancellations...")
        records = read_jsonl_folder(cancel_path)
        create_table_and_insert(conn, "billing_document_cancellations", records)

    conn.close()
    print(f"\nSQLite database created at {DB_PATH}")


def build_graph():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    G = nx.DiGraph()

    # --- Add nodes ---

    # Sales Orders
    for row in conn.execute("SELECT * FROM sales_order_headers"):
        r = dict(row)
        G.add_node(f"SalesOrder:{r['salesOrder']}", entity="SalesOrder", **r)

    # Sales Order Items
    for row in conn.execute("SELECT * FROM sales_order_items"):
        r = dict(row)
        G.add_node(f"SalesOrderItem:{r['salesOrder']}-{r['salesOrderItem']}", entity="SalesOrderItem", **r)

    # Outbound Delivery Headers
    for row in conn.execute("SELECT * FROM outbound_delivery_headers"):
        r = dict(row)
        G.add_node(f"Delivery:{r['deliveryDocument']}", entity="Delivery", **r)

    # Outbound Delivery Items
    for row in conn.execute("SELECT * FROM outbound_delivery_items"):
        r = dict(row)
        G.add_node(f"DeliveryItem:{r['deliveryDocument']}-{r['deliveryDocumentItem']}", entity="DeliveryItem", **r)

    # Billing Document Headers
    for row in conn.execute("SELECT * FROM billing_document_headers"):
        r = dict(row)
        G.add_node(f"BillingDoc:{r['billingDocument']}", entity="BillingDocument", **r)

    # Billing Document Items
    for row in conn.execute("SELECT * FROM billing_document_items"):
        r = dict(row)
        G.add_node(f"BillingItem:{r['billingDocument']}-{r['billingDocumentItem']}", entity="BillingDocumentItem", **r)

    # Journal Entries
    for row in conn.execute("SELECT * FROM journal_entries"):
        r = dict(row)
        node_id = f"JournalEntry:{r['accountingDocument']}-{r['accountingDocumentItem']}"
        G.add_node(node_id, entity="JournalEntry", **r)

    # Payments
    for row in conn.execute("SELECT * FROM payments"):
        r = dict(row)
        node_id = f"Payment:{r['accountingDocument']}-{r['accountingDocumentItem']}"
        G.add_node(node_id, entity="Payment", **r)

    # Business Partners (Customers)
    for row in conn.execute("SELECT * FROM business_partners"):
        r = dict(row)
        G.add_node(f"Customer:{r['businessPartner']}", entity="Customer", **r)

    # Products
    for row in conn.execute("SELECT * FROM products"):
        r = dict(row)
        G.add_node(f"Product:{r['product']}", entity="Product", **r)

    # Plants
    for row in conn.execute("SELECT * FROM plants"):
        r = dict(row)
        G.add_node(f"Plant:{r['plant']}", entity="Plant", **r)

    # --- Add edges ---

    # SalesOrder -> SalesOrderItem
    for row in conn.execute("SELECT salesOrder, salesOrderItem FROM sales_order_items"):
        r = dict(row)
        G.add_edge(f"SalesOrder:{r['salesOrder']}", f"SalesOrderItem:{r['salesOrder']}-{r['salesOrderItem']}", relation="HAS_ITEM")

    # SalesOrder -> Customer (soldToParty)
    for row in conn.execute("SELECT salesOrder, soldToParty FROM sales_order_headers WHERE soldToParty IS NOT NULL AND soldToParty != ''"):
        r = dict(row)
        G.add_edge(f"SalesOrder:{r['salesOrder']}", f"Customer:{r['soldToParty']}", relation="SOLD_TO")

    # SalesOrderItem -> Product (material)
    for row in conn.execute("SELECT salesOrder, salesOrderItem, material FROM sales_order_items WHERE material IS NOT NULL AND material != ''"):
        r = dict(row)
        G.add_edge(f"SalesOrderItem:{r['salesOrder']}-{r['salesOrderItem']}", f"Product:{r['material']}", relation="CONTAINS_PRODUCT")

    # SalesOrderItem -> Plant (productionPlant)
    for row in conn.execute("SELECT salesOrder, salesOrderItem, productionPlant FROM sales_order_items WHERE productionPlant IS NOT NULL AND productionPlant != ''"):
        r = dict(row)
        G.add_edge(f"SalesOrderItem:{r['salesOrder']}-{r['salesOrderItem']}", f"Plant:{r['productionPlant']}", relation="PRODUCED_AT")

    # DeliveryItem -> SalesOrder (via referenceSdDocument)
    for row in conn.execute("SELECT deliveryDocument, deliveryDocumentItem, referenceSdDocument, referenceSdDocumentItem FROM outbound_delivery_items WHERE referenceSdDocument IS NOT NULL AND referenceSdDocument != ''"):
        r = dict(row)
        G.add_edge(f"DeliveryItem:{r['deliveryDocument']}-{r['deliveryDocumentItem']}", f"SalesOrderItem:{r['referenceSdDocument']}-{r['referenceSdDocumentItem']}", relation="DELIVERS")

    # Delivery -> DeliveryItem
    for row in conn.execute("SELECT deliveryDocument, deliveryDocumentItem FROM outbound_delivery_items"):
        r = dict(row)
        G.add_edge(f"Delivery:{r['deliveryDocument']}", f"DeliveryItem:{r['deliveryDocument']}-{r['deliveryDocumentItem']}", relation="HAS_ITEM")

    # DeliveryItem -> Plant
    for row in conn.execute("SELECT deliveryDocument, deliveryDocumentItem, plant FROM outbound_delivery_items WHERE plant IS NOT NULL AND plant != ''"):
        r = dict(row)
        G.add_edge(f"DeliveryItem:{r['deliveryDocument']}-{r['deliveryDocumentItem']}", f"Plant:{r['plant']}", relation="SHIPPED_FROM")

    # BillingDoc -> BillingItem
    for row in conn.execute("SELECT billingDocument, billingDocumentItem FROM billing_document_items"):
        r = dict(row)
        G.add_edge(f"BillingDoc:{r['billingDocument']}", f"BillingItem:{r['billingDocument']}-{r['billingDocumentItem']}", relation="HAS_ITEM")

    # BillingItem -> SalesOrderItem (via referenceSdDocument)
    for row in conn.execute("SELECT billingDocument, billingDocumentItem, referenceSdDocument, referenceSdDocumentItem FROM billing_document_items WHERE referenceSdDocument IS NOT NULL AND referenceSdDocument != ''"):
        r = dict(row)
        G.add_edge(f"BillingItem:{r['billingDocument']}-{r['billingDocumentItem']}", f"SalesOrderItem:{r['referenceSdDocument']}-{r['referenceSdDocumentItem']}", relation="BILLS")

    # BillingDoc -> Customer (soldToParty)
    for row in conn.execute("SELECT billingDocument, soldToParty FROM billing_document_headers WHERE soldToParty IS NOT NULL AND soldToParty != ''"):
        r = dict(row)
        G.add_edge(f"BillingDoc:{r['billingDocument']}", f"Customer:{r['soldToParty']}", relation="BILLED_TO")

    # BillingItem -> Product (material)
    for row in conn.execute("SELECT billingDocument, billingDocumentItem, material FROM billing_document_items WHERE material IS NOT NULL AND material != ''"):
        r = dict(row)
        G.add_edge(f"BillingItem:{r['billingDocument']}-{r['billingDocumentItem']}", f"Product:{r['material']}", relation="BILLS_PRODUCT")

    # JournalEntry -> BillingDoc (via referenceDocument)
    for row in conn.execute("SELECT accountingDocument, accountingDocumentItem, referenceDocument FROM journal_entries WHERE referenceDocument IS NOT NULL AND referenceDocument != ''"):
        r = dict(row)
        ref = r['referenceDocument']
        # Check if reference doc is a billing document
        if G.has_node(f"BillingDoc:{ref}"):
            G.add_edge(f"JournalEntry:{r['accountingDocument']}-{r['accountingDocumentItem']}", f"BillingDoc:{ref}", relation="ACCOUNTS_FOR")

    # JournalEntry -> Customer
    for row in conn.execute("SELECT accountingDocument, accountingDocumentItem, customer FROM journal_entries WHERE customer IS NOT NULL AND customer != ''"):
        r = dict(row)
        G.add_edge(f"JournalEntry:{r['accountingDocument']}-{r['accountingDocumentItem']}", f"Customer:{r['customer']}", relation="RECEIVABLE_FROM")

    # Payment -> Customer
    for row in conn.execute("SELECT accountingDocument, accountingDocumentItem, customer FROM payments WHERE customer IS NOT NULL AND customer != ''"):
        r = dict(row)
        G.add_edge(f"Payment:{r['accountingDocument']}-{r['accountingDocumentItem']}", f"Customer:{r['customer']}", relation="PAID_BY")

    # Payment -> BillingDoc (via invoiceReference)
    for row in conn.execute("SELECT accountingDocument, accountingDocumentItem, invoiceReference FROM payments WHERE invoiceReference IS NOT NULL AND invoiceReference != ''"):
        r = dict(row)
        ref = r['invoiceReference']
        if G.has_node(f"BillingDoc:{ref}"):
            G.add_edge(f"Payment:{r['accountingDocument']}-{r['accountingDocumentItem']}", f"BillingDoc:{ref}", relation="PAYS_INVOICE")

    # Product -> Plant (via product_plants)
    for row in conn.execute("SELECT product, plant FROM product_plants"):
        r = dict(row)
        if G.has_node(f"Product:{r['product']}") and G.has_node(f"Plant:{r['plant']}"):
            G.add_edge(f"Product:{r['product']}", f"Plant:{r['plant']}", relation="AVAILABLE_AT")

    conn.close()

    print(f"\nGraph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # Save graph
    with open(GRAPH_PATH, "wb") as f:
        pickle.dump(G, f)
    print(f"Graph saved to {GRAPH_PATH}")

    # Print summary
    entity_counts = {}
    for _, data in G.nodes(data=True):
        etype = data.get("entity", "Unknown")
        entity_counts[etype] = entity_counts.get(etype, 0) + 1
    print("\nNode counts by entity type:")
    for etype, count in sorted(entity_counts.items()):
        print(f"  {etype}: {count}")

    edge_counts = {}
    for _, _, data in G.edges(data=True):
        rel = data.get("relation", "Unknown")
        edge_counts[rel] = edge_counts.get(rel, 0) + 1
    print("\nEdge counts by relation:")
    for rel, count in sorted(edge_counts.items()):
        print(f"  {rel}: {count}")

    return G


if __name__ == "__main__":
    print("=== Ingesting data to SQLite ===")
    ingest_to_sqlite()
    print("\n=== Building graph ===")
    build_graph()
