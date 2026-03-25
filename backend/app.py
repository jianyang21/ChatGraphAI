"""
ChatGraph AI backend.
Graph data API + LLM-powered query interface for SAP O2C data.
"""

import os
import json
import sqlite3
import pickle
import re
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = FastAPI(title="ChatGraph AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "o2c.db")
GRAPH_PATH = os.path.join(os.path.dirname(__file__), "graph.gpickle")

with open(GRAPH_PATH, "rb") as f:
    GRAPH = pickle.load(f)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
MODEL_NAME = "llama-3.1-8b-instant"

DB_SCHEMA = """
Tables in the SQLite database:

1. sales_order_headers (salesOrder, salesOrderType, salesOrganization, distributionChannel, organizationDivision, soldToParty, creationDate, createdByUser, lastChangeDateTime, totalNetAmount, overallDeliveryStatus, transactionCurrency, pricingDate, requestedDeliveryDate, incotermsClassification, customerPaymentTerms)
   - Primary key: salesOrder
   - soldToParty references business_partners.businessPartner

2. sales_order_items (salesOrder, salesOrderItem, salesOrderItemCategory, material, requestedQuantity, requestedQuantityUnit, transactionCurrency, netAmount, materialGroup, productionPlant, storageLocation, salesDocumentRjcnReason, itemBillingBlockReason)
   - Primary key: (salesOrder, salesOrderItem)
   - salesOrder references sales_order_headers.salesOrder
   - material references products.product
   - productionPlant references plants.plant

3. sales_order_schedule_lines (salesOrder, salesOrderItem, scheduleLine, confirmedDeliveryDate, orderQuantityUnit, confdOrderQtyByMatlAvailCheck)
   - Primary key: (salesOrder, salesOrderItem, scheduleLine)

4. outbound_delivery_headers (deliveryDocument, creationDate, creationTime, actualGoodsMovementDate, actualGoodsMovementTime, shippingPoint, overallGoodsMovementStatus, overallPickingStatus, deliveryBlockReason, headerBillingBlockReason, hdrGeneralIncompletionStatus, lastChangeDate, overallProofOfDeliveryStatus)
   - Primary key: deliveryDocument

5. outbound_delivery_items (deliveryDocument, deliveryDocumentItem, actualDeliveryQuantity, deliveryQuantityUnit, batch, plant, storageLocation, referenceSdDocument, referenceSdDocumentItem, itemBillingBlockReason, lastChangeDate)
   - Primary key: (deliveryDocument, deliveryDocumentItem)
   - referenceSdDocument references sales_order_headers.salesOrder
   - referenceSdDocumentItem references sales_order_items.salesOrderItem
   - plant references plants.plant

6. billing_document_headers (billingDocument, billingDocumentType, creationDate, creationTime, lastChangeDateTime, billingDocumentDate, billingDocumentIsCancelled, cancelledBillingDocument, totalNetAmount, transactionCurrency, companyCode, fiscalYear, accountingDocument, soldToParty)
   - Primary key: billingDocument
   - soldToParty references business_partners.businessPartner

7. billing_document_items (billingDocument, billingDocumentItem, material, billingQuantity, billingQuantityUnit, netAmount, transactionCurrency, referenceSdDocument, referenceSdDocumentItem)
   - Primary key: (billingDocument, billingDocumentItem)
   - referenceSdDocument references sales_order_headers.salesOrder
   - material references products.product

8. journal_entries (companyCode, fiscalYear, accountingDocument, glAccount, referenceDocument, costCenter, profitCenter, transactionCurrency, amountInTransactionCurrency, companyCodeCurrency, amountInCompanyCodeCurrency, postingDate, documentDate, accountingDocumentType, accountingDocumentItem, customer, financialAccountType, clearingDate, clearingAccountingDocument, clearingDocFiscalYear)
   - Primary key: (companyCode, fiscalYear, accountingDocument, accountingDocumentItem)
   - referenceDocument references billing_document_headers.billingDocument
   - customer references business_partners.businessPartner

9. payments (companyCode, fiscalYear, accountingDocument, accountingDocumentItem, clearingDate, clearingAccountingDocument, clearingDocFiscalYear, amountInTransactionCurrency, transactionCurrency, amountInCompanyCodeCurrency, companyCodeCurrency, customer, invoiceReference, invoiceReferenceFiscalYear, salesDocument, salesDocumentItem, postingDate, documentDate, assignmentReference, glAccount, financialAccountType, profitCenter, costCenter)
   - Primary key: (companyCode, fiscalYear, accountingDocument, accountingDocumentItem)
   - customer references business_partners.businessPartner
   - invoiceReference may reference billing_document_headers.billingDocument

10. business_partners (businessPartner, customer, businessPartnerCategory, businessPartnerFullName, businessPartnerGrouping, businessPartnerName, correspondenceLanguage, createdByUser, creationDate, creationTime, firstName, formOfAddress, industry, lastChangeDate, lastName, organizationBpName1, organizationBpName2, businessPartnerIsBlocked, isMarkedForArchiving)
    - Primary key: businessPartner

11. business_partner_addresses (businessPartner, addressId, validityStartDate, validityEndDate, cityName, country, postalCode, region, streetName, poBox, poBoxPostalCode, addressTimeZone, transportZone, taxJurisdiction, addressUuid, poBoxDeviatingCityName, poBoxDeviatingCountry, poBoxDeviatingRegion, poBoxIsWithoutNumber, poBoxLobbyName)
    - Primary key: (businessPartner, addressId)

12. customer_company_assignments (customer, companyCode, accountingClerk, paymentTerms, reconciliationAccount, paymentMethodsList, paymentBlockingReason, deletionIndicator, customerAccountGroup, alternativePayerAccount, accountingClerkFaxNumber, accountingClerkInternetAddress, accountingClerkPhoneNumber)
    - Primary key: (customer, companyCode)

13. customer_sales_area_assignments (customer, salesOrganization, distributionChannel, division, currency, customerPaymentTerms, incotermsClassification, incotermsLocation1, deliveryPriority, shippingCondition, completeDeliveryIsDefined, billingIsBlockedForCustomer, creditControlArea, salesGroup, salesOffice, supplyingPlant, salesDistrict, exchangeRateType, slsUnlmtdOvrdelivIsAllwd)
    - Primary key: (customer, salesOrganization, distributionChannel, division)

14. products (product, productType, crossPlantStatus, crossPlantStatusValidityDate, creationDate, createdByUser, lastChangeDate, lastChangeDateTime, isMarkedForDeletion, productOldId, grossWeight, weightUnit, netWeight, productGroup, baseUnit, division, industrySector)
    - Primary key: product

15. product_descriptions (product, language, productDescription)
    - Primary key: (product, language)

16. product_plants (product, plant, countryOfOrigin, regionOfOrigin, productionInvtryManagedLoc, availabilityCheckType, fiscalYearVariant, profitCenter, mrpType)
    - Primary key: (product, plant)

17. product_storage_locations (product, plant, storageLocation, physicalInventoryBlockInd, dateOfLastPostedCntUnRstrcdStk)
    - Primary key: (product, plant, storageLocation)

18. plants (plant, plantName, valuationArea, plantCustomer, plantSupplier, factoryCalendar, defaultPurchasingOrganization, salesOrganization, addressId, plantCategory, distributionChannel, division, language, isMarkedForArchiving)
    - Primary key: plant

19. billing_document_cancellations (same schema as billing_document_headers)

Key Relationships (Order to Cash flow):
- Sales Order -> Sales Order Items (salesOrder)
- Sales Order Items -> Outbound Delivery Items (via outbound_delivery_items.referenceSdDocument = salesOrder)
- Outbound Delivery Items -> Billing Document Items (via billing_document_items.referenceSdDocument = salesOrder)
- Billing Document -> Journal Entries (via journal_entries.referenceDocument = billingDocument)
- Journal Entries / Payments -> Customer (via customer field)

All monetary amounts are in INR (Indian Rupees).
All IDs are stored as TEXT.
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn



@app.get("/api/graph/summary")
def graph_summary():
    entity_counts = {}
    for _, data in GRAPH.nodes(data=True):
        etype = data.get("entity", "Unknown")
        entity_counts[etype] = entity_counts.get(etype, 0) + 1

    edge_counts = {}
    for _, _, data in GRAPH.edges(data=True):
        rel = data.get("relation", "Unknown")
        edge_counts[rel] = edge_counts.get(rel, 0) + 1

    return {
        "total_nodes": GRAPH.number_of_nodes(),
        "total_edges": GRAPH.number_of_edges(),
        "entity_counts": entity_counts,
        "edge_counts": edge_counts,
    }


@app.get("/api/graph/nodes")
def get_graph_nodes(entity_type: Optional[str] = None, limit: int = 500):
    nodes = []
    for node_id, data in GRAPH.nodes(data=True):
        if entity_type and data.get("entity") != entity_type:
            continue
        nodes.append({
            "id": node_id,
            "entity": data.get("entity", "Unknown"),
            "label": _get_node_label(node_id, data),
        })
        if len(nodes) >= limit:
            break
    return nodes


@app.get("/api/graph/node/{node_id:path}")
def get_node_detail(node_id: str):
    if node_id not in GRAPH:
        raise HTTPException(status_code=404, detail="Node not found")

    data = dict(GRAPH.nodes[node_id])

    neighbors = []
    for neighbor in GRAPH.successors(node_id):
        edge_data = GRAPH.edges[node_id, neighbor]
        neighbors.append({
            "id": neighbor,
            "entity": GRAPH.nodes[neighbor].get("entity", "Unknown"),
            "label": _get_node_label(neighbor, GRAPH.nodes[neighbor]),
            "relation": edge_data.get("relation", ""),
            "direction": "outgoing",
        })
    for neighbor in GRAPH.predecessors(node_id):
        edge_data = GRAPH.edges[neighbor, node_id]
        neighbors.append({
            "id": neighbor,
            "entity": GRAPH.nodes[neighbor].get("entity", "Unknown"),
            "label": _get_node_label(neighbor, GRAPH.nodes[neighbor]),
            "relation": edge_data.get("relation", ""),
            "direction": "incoming",
        })

    return {
        "id": node_id,
        "entity": data.get("entity", "Unknown"),
        "label": _get_node_label(node_id, data),
        "properties": {k: v for k, v in data.items() if k != "entity"},
        "connections": neighbors,
        "connection_count": len(neighbors),
    }


@app.get("/api/graph/subgraph/{node_id:path}")
def get_subgraph(node_id: str, depth: int = 1):
    if node_id not in GRAPH:
        raise HTTPException(status_code=404, detail="Node not found")

    visited = {node_id}
    frontier = {node_id}
    for _ in range(depth):
        next_frontier = set()
        for n in frontier:
            for neighbor in GRAPH.successors(n):
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
            for neighbor in GRAPH.predecessors(n):
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
        frontier = next_frontier

    nodes = []
    for n in visited:
        data = GRAPH.nodes[n]
        nodes.append({
            "id": n,
            "entity": data.get("entity", "Unknown"),
            "label": _get_node_label(n, data),
        })

    edges = []
    for u, v, data in GRAPH.edges(data=True):
        if u in visited and v in visited:
            edges.append({
                "source": u,
                "target": v,
                "relation": data.get("relation", ""),
            })

    return {"nodes": nodes, "edges": edges}


@app.get("/api/graph/overview")
def get_graph_overview():
    entity_samples = {}
    for node_id, data in GRAPH.nodes(data=True):
        etype = data.get("entity", "Unknown")
        if etype == "Unknown":
            continue
        if etype not in entity_samples:
            entity_samples[etype] = []
        if len(entity_samples[etype]) < _sample_limit(etype):
            entity_samples[etype].append(node_id)

    sampled_ids = set()
    for ids in entity_samples.values():
        sampled_ids.update(ids)

    nodes = []
    for n in sampled_ids:
        data = GRAPH.nodes[n]
        nodes.append({
            "id": n,
            "entity": data.get("entity", "Unknown"),
            "label": _get_node_label(n, data),
        })

    edges = []
    for u, v, data in GRAPH.edges(data=True):
        if u in sampled_ids and v in sampled_ids:
            edges.append({
                "source": u,
                "target": v,
                "relation": data.get("relation", ""),
            })

    return {"nodes": nodes, "edges": edges}


def _sample_limit(entity_type: str) -> int:
    limits = {
        "SalesOrder": 20,
        "SalesOrderItem": 30,
        "Delivery": 15,
        "DeliveryItem": 25,
        "BillingDocument": 20,
        "BillingDocumentItem": 30,
        "JournalEntry": 15,
        "Payment": 15,
        "Customer": 8,
        "Product": 15,
        "Plant": 10,
    }
    return limits.get(entity_type, 10)


@app.get("/api/graph/search")
def search_nodes(q: str, limit: int = 20):
    q_lower = q.lower()
    results = []
    for node_id, data in GRAPH.nodes(data=True):
        label = _get_node_label(node_id, data)
        if q_lower in node_id.lower() or q_lower in label.lower():
            results.append({
                "id": node_id,
                "entity": data.get("entity", "Unknown"),
                "label": label,
            })
            if len(results) >= limit:
                break
    return results


def _get_node_label(node_id: str, data: dict) -> str:
    entity = data.get("entity", "")
    if entity == "SalesOrder":
        return f"SO {data.get('salesOrder', '')}"
    elif entity == "SalesOrderItem":
        return f"SO Item {data.get('salesOrder', '')}-{data.get('salesOrderItem', '')}"
    elif entity == "Delivery":
        return f"Del {data.get('deliveryDocument', '')}"
    elif entity == "DeliveryItem":
        return f"Del Item {data.get('deliveryDocument', '')}-{data.get('deliveryDocumentItem', '')}"
    elif entity == "BillingDocument":
        return f"Bill {data.get('billingDocument', '')}"
    elif entity == "BillingDocumentItem":
        return f"Bill Item {data.get('billingDocument', '')}-{data.get('billingDocumentItem', '')}"
    elif entity == "JournalEntry":
        return f"JE {data.get('accountingDocument', '')}-{data.get('accountingDocumentItem', '')}"
    elif entity == "Payment":
        return f"Pay {data.get('accountingDocument', '')}-{data.get('accountingDocumentItem', '')}"
    elif entity == "Customer":
        name = data.get('businessPartnerFullName') or data.get('businessPartnerName') or data.get('businessPartner', '')
        return f"Cust {name}"
    elif entity == "Product":
        return f"Prod {data.get('product', '')}"
    elif entity == "Plant":
        return f"Plant {data.get('plantName') or data.get('plant', '')}"
    return node_id.split(":")[-1] if ":" in node_id else node_id



class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] = []


class ChatResponse(BaseModel):
    answer: str
    sql_query: Optional[str] = None
    query_results: Optional[list[dict]] = None
    referenced_nodes: list[str] = []


SYSTEM_PROMPT = f"""You are a data analyst assistant for an SAP Order-to-Cash (O2C) system. You help users query and understand business data about sales orders, deliveries, billing documents, journal entries, payments, customers, products, and plants.

IMPORTANT RULES:
1. You MUST ONLY answer questions related to the SAP Order-to-Cash dataset. If a user asks about anything unrelated (general knowledge, creative writing, coding help, etc.), respond EXACTLY with: "This system is designed to answer questions related to the SAP Order-to-Cash dataset only. Please ask questions about sales orders, deliveries, billing, payments, customers, or products."
2. You translate user questions into SQL queries against a SQLite database.
3. Your responses must be grounded in actual query results - never fabricate data.
4. Return your response in this JSON format:
{{{{
  "sql": "THE SQL QUERY",
  "explanation": "Brief natural language answer based on the results"
}}}}

If the question doesn't need SQL (e.g., asking about the schema), set sql to null and just provide the explanation.

DATABASE SCHEMA:
{DB_SCHEMA}

GUIDELINES FOR SQL:
- All columns are TEXT type, so use CAST() for numeric comparisons: CAST(totalNetAmount AS REAL)
- For date comparisons, dates are in format 'YYYY-MM-DD' or ISO format with T
- Use proper JOINs to trace the O2C flow
- Limit results to 50 rows unless the user asks for more
- For aggregations, always include meaningful labels

EXAMPLE QUERIES:

Q: "Which products have the most billing documents?"
SQL: SELECT bi.material AS product, COUNT(DISTINCT bi.billingDocument) AS billing_count FROM billing_document_items bi WHERE bi.material IS NOT NULL AND bi.material != '' GROUP BY bi.material ORDER BY billing_count DESC LIMIT 10

Q: "Trace the full flow of billing document 91150187"
SQL: SELECT 'BillingDoc' AS step, bh.billingDocument AS id, bh.totalNetAmount AS amount, bh.creationDate FROM billing_document_headers bh WHERE bh.billingDocument = '91150187' UNION ALL SELECT 'SalesOrder' AS step, soh.salesOrder AS id, soh.totalNetAmount AS amount, soh.creationDate FROM sales_order_headers soh WHERE soh.salesOrder IN (SELECT DISTINCT bi.referenceSdDocument FROM billing_document_items bi WHERE bi.billingDocument = '91150187') UNION ALL SELECT 'Delivery' AS step, odh.deliveryDocument AS id, '' AS amount, odh.creationDate FROM outbound_delivery_headers odh WHERE odh.deliveryDocument IN (SELECT DISTINCT odi.deliveryDocument FROM outbound_delivery_items odi WHERE odi.referenceSdDocument IN (SELECT DISTINCT bi.referenceSdDocument FROM billing_document_items bi WHERE bi.billingDocument = '91150187')) UNION ALL SELECT 'JournalEntry' AS step, je.accountingDocument AS id, je.amountInTransactionCurrency AS amount, je.postingDate AS creationDate FROM journal_entries je WHERE je.referenceDocument = '91150187'

Q: "Find sales orders that were delivered but not billed"
SQL: SELECT DISTINCT soh.salesOrder, soh.totalNetAmount, soh.creationDate, soh.soldToParty FROM sales_order_headers soh INNER JOIN sales_order_items soi ON soh.salesOrder = soi.salesOrder INNER JOIN outbound_delivery_items odi ON odi.referenceSdDocument = soi.salesOrder AND odi.referenceSdDocumentItem = soi.salesOrderItem LEFT JOIN billing_document_items bi ON bi.referenceSdDocument = soi.salesOrder AND bi.referenceSdDocumentItem = soi.salesOrderItem WHERE bi.billingDocument IS NULL LIMIT 50
"""


def is_off_topic(message: str) -> bool:
    off_topic_patterns = [
        r'\b(weather|recipe|joke|poem|story|song|movie|game|sport)\b',
        r'\b(who is|what is the capital|translate|write me a)\b',
        r'\b(python|javascript|code|programming)\b',
        r'\b(hello|hi|hey|how are you)\b',
    ]
    msg_lower = message.lower()
    dataset_terms = ['order', 'sales', 'delivery', 'billing', 'invoice', 'payment',
                     'customer', 'product', 'plant', 'journal', 'material', 'document',
                     'o2c', 'sap', 'flow', 'trace', 'amount', 'query']
    has_dataset_term = any(term in msg_lower for term in dataset_terms)
    if has_dataset_term:
        return False
    for pattern in off_topic_patterns:
        if re.search(pattern, msg_lower):
            return True
    return False


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if is_off_topic(req.message):
        return ChatResponse(
            answer="This system is designed to answer questions related to the SAP Order-to-Cash dataset only. Please ask questions about sales orders, deliveries, billing, payments, customers, or products.",
            referenced_nodes=[],
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    for msg in req.conversation_history[-6:]:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    messages.append({"role": "user", "content": req.message})

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.2,
        )

        response_text = response.choices[0].message.content.strip()

        # Parse JSON from response
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            json_match = re.search(r'\{[^{}]*"sql"[^{}]*"explanation"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            if "designed to answer" in response_text.lower() or "not related" in response_text.lower():
                return ChatResponse(
                    answer="This system is designed to answer questions related to the SAP Order-to-Cash dataset only. Please ask questions about sales orders, deliveries, billing, payments, customers, or products.",
                    referenced_nodes=[],
                )
            return ChatResponse(answer=response_text, referenced_nodes=[])

        sql_query = parsed.get("sql")
        explanation = parsed.get("explanation", "")
        query_results = None
        referenced_nodes = []

        if sql_query:
            sql_clean = sql_query.strip().upper()
            if not sql_clean.startswith("SELECT") and not sql_clean.startswith("WITH"):
                return ChatResponse(
                    answer="I can only execute SELECT queries for safety reasons.",
                    referenced_nodes=[],
                )

            dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "ATTACH", "DETACH"]
            if any(f" {d} " in f" {sql_clean} " for d in dangerous):
                return ChatResponse(
                    answer="I can only execute read-only queries.",
                    referenced_nodes=[],
                )

            try:
                conn = get_db()
                cursor = conn.execute(sql_query)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                conn.close()

                query_results = [dict(zip(columns, row)) for row in rows]
                referenced_nodes = _extract_node_ids(query_results)

                if query_results:
                    summary_prompt = f"""Based on this SQL query and its results, provide a clear natural language answer.

Query: {sql_query}
Results (first 20 rows): {json.dumps(query_results[:20], default=str)}
Total rows: {len(query_results)}

Original question: {req.message}

Provide a concise, data-backed answer. Use specific numbers from the results. Format nicely with bullet points if showing multiple items."""

                    summary_response = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[{"role": "user", "content": summary_prompt}],
                        temperature=0.2,
                    )

                    explanation = summary_response.choices[0].message.content.strip()

            except Exception as e:
                explanation = f"SQL query failed: {str(e)}\n\nGenerated query was:\n```sql\n{sql_query}\n```\n\nPlease try rephrasing your question."

        return ChatResponse(
            answer=explanation,
            sql_query=sql_query,
            query_results=query_results[:50] if query_results else None,
            referenced_nodes=referenced_nodes,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")


def _extract_node_ids(results: list[dict]) -> list[str]:
    node_ids = []
    for row in results[:50]:
        for key, value in row.items():
            if value is None:
                continue
            val = str(value)
            key_lower = key.lower()
            if "salesorder" in key_lower and "item" not in key_lower:
                nid = f"SalesOrder:{val}"
                if GRAPH.has_node(nid):
                    node_ids.append(nid)
            elif "deliverydocument" in key_lower and "item" not in key_lower:
                nid = f"Delivery:{val}"
                if GRAPH.has_node(nid):
                    node_ids.append(nid)
            elif "billingdocument" in key_lower and "item" not in key_lower:
                nid = f"BillingDoc:{val}"
                if GRAPH.has_node(nid):
                    node_ids.append(nid)
            elif key_lower == "product" or key_lower == "material":
                nid = f"Product:{val}"
                if GRAPH.has_node(nid):
                    node_ids.append(nid)
            elif key_lower in ("businesspartner", "customer", "soldtoparty"):
                nid = f"Customer:{val}"
                if GRAPH.has_node(nid):
                    node_ids.append(nid)
            elif key_lower == "plant":
                nid = f"Plant:{val}"
                if GRAPH.has_node(nid):
                    node_ids.append(nid)
    return list(set(node_ids))



@app.get("/api/health")
def health():
    return {"status": "ok", "nodes": GRAPH.number_of_nodes(), "edges": GRAPH.number_of_edges()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
