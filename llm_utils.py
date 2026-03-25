"""
LLM Integration for Natural Language to SQL Translation
Uses Groq API (Python 3.14 compatible, free tier)
"""

import os
import json
import sqlite3
import asyncio
from typing import Dict, List, Tuple, Any, Optional
import networkx as nx
from groq import Groq

# Initialize Groq client lazily (when first needed)
_groq_client = None

def get_groq_client():
    """Get or initialize the Groq client (lazy initialization)."""
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        _groq_client = Groq(api_key=api_key)
    return _groq_client

# ============================================================================
# CONSTANTS & GUARDRAILS
# ============================================================================

ALLOWED_TABLES = {
    'sales_order_headers',
    'sales_order_items',
    'outbound_delivery_headers',
    'outbound_delivery_items',
    'billing_document_headers',
    'billing_document_items',
    'billing_document_cancellations',
    'journal_entry_items_accounts_receivable',
    'payments_accounts_receivable',
    'business_partners',
    'business_partner_addresses',
    'products',
    'product_descriptions',
    'plants',
    'product_plants',
    'product_storage_locations',
    'customer_company_assignments',
    'customer_sales_area_assignments',
}

FORBIDDEN_KEYWORDS = [
    'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 
    'CREATE', 'REPLACE', 'TRUNCATE', 'ATTACH', 'DETACH'
]

SYSTEM_PROMPT = """You are an expert SQL analyst for an Order-to-Cash (O2C) business process system.

Your role:
1. Translate natural language questions about orders, deliveries, billing, and payments into SQL queries
2. Only use SELECT statements - NO modifications allowed
3. Only query the allowed tables in the O2C database
4. Generate clean, efficient SQL

Important constraints:
- You MUST ONLY generate SELECT queries
- You MUST validate that queries only touch allowed tables
- If a query would be unsafe or touches forbidden tables, respond with: "UNSAFE_QUERY"
- If the user asks about non-O2C topics, respond with: "OUT_OF_SCOPE"

Database schema (key tables and relationships):
- billing_document_items: Contains line item details (columns: billingdocument, product, totalamount, netamount, material)
- billing_document_headers: Billing header info (columns: billingdocument, soldtoparty, createddate)
- products: Product master data (columns: product, productdescription)
- sales_order_items: Sales order lines (columns: salesorder, product, orderquantity)
- sales_order_headers: Sales order headers (columns: salesorder, soldtoparty)
- business_partners: Customer/vendor data (columns: businesspartner, businesspartnername, partnername)
- outbound_delivery_headers: Delivery headers (columns: deliverydocument, soldtoparty)
- outbound_delivery_items: Delivery lines (columns: deliverydocument, product)
- journal_entry_items_accounts_receivable: Accounting entries (columns: accountingdocument, amount, documenttype)
- payments_accounts_receivable: Payment records (columns: accountingdocument, amount)

CRITICAL - Use exact column names:
- Use "material" NOT "product" for material codes in billing_document_items
- Use "businesspartnername" in business_partners table
- Join hints:
  * billing_document_items → business_partners: via billing_document_headers.soldtoparty = business_partners.businesspartner
  * billing_document_items → products: via material = product (sometimes)
  * sales_order_items → business_partners: via sales_order_headers.soldtoparty = business_partners.businesspartner
  * billing_document_items → sales_order_items: via product/material common field

Example query patterns:
1. For "highest billing products": 
   SELECT material, COUNT(DISTINCT billingdocument) as count
   FROM billing_document_items 
   GROUP BY material 
   ORDER BY count DESC

2. For revenue by customer:
   SELECT bp.businesspartnername, SUM(CAST(bdi.netamount AS FLOAT)) as total
   FROM billing_document_items bdi
   JOIN billing_document_headers bdh ON bdi.billingdocument = bdh.billingdocument
   JOIN business_partners bp ON bdh.soldtoparty = bp.businesspartner
   GROUP BY bp.businesspartnername
   ORDER BY total DESC

When user asks a question:
1. Identify the entities involved (products, orders, billing, etc)
2. Determine the correct joins based on product codes or document IDs
3. Generate the SELECT query with proper aggregations if needed
4. Include relevant business logic (e.g., SUM for amounts, COUNT for quantities)
5. Always CAST numeric-looking columns to numbers for calculations

Return ONLY the SQL query, nothing else. Do not include markdown, backticks, or explanations."""

SYNTHESIS_PROMPT = """You are a business analyst synthesizing results from the Order-to-Cash system.

Your task:
1. The user asked a question about O2C data
2. A SQL query was executed
3. You received the results
4. Now synthesize a clear, business-friendly response

Guidelines:
- Ground your response ONLY in the provided data
- Be concise and factual
- Highlight key numbers and insights
- If results are empty, explain why
- Reference specific entities (order IDs, amounts, dates) from the results

Do NOT:
- Speculate beyond the data
- Make assumptions
- Invent information

Format your response naturally, as if explaining to a business stakeholder."""

# ============================================================================
# GUARD RAILS
# ============================================================================

def validate_sql_query(sql_query: str) -> Tuple[bool, str]:
    """Validate SQL query for safety."""
    
    # Check for forbidden keywords
    query_upper = sql_query.upper()
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in query_upper:
            return False, f"Forbidden operation: {keyword}"
    
    # Check for SELECT
    if not query_upper.strip().startswith('SELECT'):
        return False, "Only SELECT queries allowed"
    
    # Check for allowed tables
    for forbidden in ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'PRAGMA']:
        if forbidden in query_upper:
            return False, f"Forbidden keyword: {forbidden}"
    
    return True, ""

def extract_tables_from_query(sql_query: str) -> set:
    """Extract table names from SQL query."""
    import re
    
    # Basic regex to extract table names after FROM and JOIN keywords
    pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    tables = set(re.findall(pattern, sql_query, re.IGNORECASE))
    
    return tables

def is_query_safe(sql_query: str) -> Tuple[bool, str]:
    """Full validation of SQL query."""
    
    # Validate structure
    is_valid, msg = validate_sql_query(sql_query)
    if not is_valid:
        return False, msg
    
    # Extract and validate tables
    tables = extract_tables_from_query(sql_query)
    for table in tables:
        if table not in ALLOWED_TABLES:
            return False, f"Access denied to table: {table}"
    
    return True, ""

def is_query_in_scope(user_query: str) -> bool:
    """Check if user query is about O2C domain."""
    
    # Keywords that indicate O2C domain
    in_scope_keywords = [
        'order', 'sales', 'delivery', 'billing', 'invoice',
        'payment', 'customer', 'product', 'material', 'shipment',
        'accounts', 'receivable', 'journal', 'accounting', 'transaction',
        'flow', 'trace', 'document', 'quantity', 'amount', 'date',
        'plant', 'warehouse', 'storage', 'partner', 'vendor', 'revenue',
        'broken', 'incomplete', 'associated', 'generate', 'identify',
        'top', 'highest', 'most', 'count', 'number'
    ]
    
    query_lower = user_query.lower()
    
    # Check if any O2C keyword appears
    has_o2c_keyword = any(kw in query_lower for kw in in_scope_keywords)
    
    # Out-of-scope: general knowledge, creative writing, unrelated topics
    out_of_scope_keywords = [
        'write a poem', 'tell me a joke', 'recipe', 'movie', 'music',
        'weather', 'sports', 'politics', 'philosophy', 'history of the world',
        'how to make', 'what is the capital', 'who is', 'general knowledge'
    ]
    is_out_of_scope = any(kw in query_lower for kw in out_of_scope_keywords)
    
    return has_o2c_keyword and not is_out_of_scope

# ============================================================================
# LLM INTERACTION
# ============================================================================

async def generate_sql_from_query(
    user_query: str,
    table_schemas: Dict[str, List[str]],
    db_conn: sqlite3.Connection
) -> str:
    """Generate SQL from natural language using Groq LLM."""
    
    # Guard rail: Check if query is in scope
    if not is_query_in_scope(user_query):
        raise ValueError("This system is designed to answer questions related to the Order-to-Cash dataset only.")
    
    # Build context about available tables
    schema_info = "Available tables and columns:\n"
    for table, columns in list(table_schemas.items())[:10]:  # Limit to first 10 for context
        schema_info += f"\n{table}:\n"
        schema_info += f"  Columns: {', '.join(columns[:15])}\n"  # Limit columns shown
    
    # Prepare the message for LLM
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT + "\n\n" + schema_info
        },
        {
            "role": "user",
            "content": f"Generate a SQL query for: {user_query}"
        }
    ]
    
    # Call Groq API
    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )
        
        sql_query = response.choices[0].message.content.strip()
        
        # Check for safety signals
        if "UNSAFE_QUERY" in sql_query or "OUT_OF_SCOPE" in sql_query:
            raise ValueError("Query not allowed: " + sql_query)
        
        # Validate the generated SQL
        is_safe, safety_msg = is_query_safe(sql_query)
        if not is_safe:
            raise ValueError(f"Generated query is unsafe: {safety_msg}")
        
        return sql_query
    
    except Exception as e:
        raise ValueError(f"Failed to generate SQL: {str(e)}")

def execute_query_safely(db_conn: sqlite3.Connection, sql_query: str, limit: int = 1000) -> List[Dict]:
    """Execute SQL query safely with error handling."""
    
    # Add LIMIT if not present
    if 'LIMIT' not in sql_query.upper():
        sql_query = sql_query.rstrip(';') + f' LIMIT {limit}'
    
    try:
        cursor = db_conn.cursor()
        cursor.execute(sql_query)
        
        # Fetch results as dicts
        columns = [desc[0] for desc in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            result_dict = dict(zip(columns, row))
            results.append(result_dict)
        
        return results
    
    except sqlite3.Error as e:
        raise ValueError(f"Database query error: {str(e)}")

async def synthesize_response(
    user_query: str,
    sql_query: str,
    results: List[Dict],
    graph: Optional[nx.DiGraph] = None
) -> Tuple[str, List[str]]:
    """Synthesize LLM response from query results."""
    
    # Format results for LLM
    results_summary = json.dumps(results[:20], indent=2)  # Limit to first 20 results
    
    # Prepare the synthesis message
    messages = [
        {
            "role": "system",
            "content": SYNTHESIS_PROMPT
        },
        {
            "role": "user",
            "content": f"""
User Question: {user_query}

SQL Query Used: {sql_query}

Query Results:
{results_summary}

Please synthesize these results into a clear, business-friendly response.
If results are empty, explain what the query was looking for.
Reference specific numbers, orders, amounts, and entities from the results.
"""
        }
    ]
    
    # Call LLM for synthesis
    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.5,
            max_tokens=1000,
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Extract referenced entities from results
        referenced_nodes = []
        for result in results[:5]:  # Check first 5 results
            for key, value in result.items():
                if value and isinstance(value, (str, int)):
                    referenced_nodes.append(str(value))
        
        return response_text, referenced_nodes
    
    except Exception as e:
        # Fallback response if synthesis fails
        if results:
            count = len(results)
            response_text = f"Found {count} matching records. {json.dumps(results[0], indent=2)}"
        else:
            response_text = "No results found for your query."
        
        return response_text, []

# ============================================================================
# GRAPH-BASED QUERY RESOLUTION (Multi-hop queries)
# ============================================================================

def detect_query_requires_graph(user_query: str) -> bool:
    """Detect if query requires graph traversal for multi-hop relationships."""
    
    # Multi-hop patterns that need graph traversal
    multihop_keywords = [
        'order.*invoice', 'order.*journal', 'order.*payment',
        'product.*customer', 'product.*partner',
        'customer.*invoice', 'customer.*delivery',
        'delivery.*invoice', 'delivery.*billing',
        'invoice.*journal', 'billing.*journal',
        'sales.*invoice', 'sales.*payment',
        'broken.*flow', 'incomplete.*flow', 'incomplete', 'broken'
    ]
    
    query_lower = user_query.lower()
    
    # Check for multi-hop patterns
    import re
    for pattern in multihop_keywords:
        if re.search(pattern, query_lower):
            return True
    
    return False

def graph_traverse_for_path(graph: nx.DiGraph, source_type: str, target_type: str, 
                            start_id: Optional[str] = None) -> List[Dict]:
    """Generic graph traversal to find paths between entity types."""
    
    if not graph:
        return []
    
    results = []
    
    # Find all nodes of source type
    source_nodes = [n for n in graph.nodes() if graph.nodes[n].get('type') == source_type]
    
    for source_node in source_nodes[:10]:  # Limit to first 10
        # Find paths to target type
        try:
            # Simple BFS to find connected target nodes
            for target_node in graph.nodes():
                if graph.nodes[target_node].get('type') == target_type:
                    if nx.has_path(graph, source_node, target_node):
                        path = nx.shortest_path(graph, source_node, target_node)
                        results.append({
                            'source_id': source_node,
                            'source_type': source_type,
                            'target_id': target_node,
                            'target_type': target_type,
                            'path_length': len(path),
                            'path': ' → '.join(path[:5])  # Limit path display
                        })
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
    
    return results

def find_broken_flows(graph: nx.DiGraph, db_conn: sqlite3.Connection) -> List[Dict]:
    """Find orders with broken or incomplete order-to-cash flows."""
    
    if not graph:
        return []
    
    broken_flows = []
    
    # Get all sales orders
    cursor = db_conn.cursor()
    cursor.execute("SELECT DISTINCT salesorder FROM sales_order_items LIMIT 50")
    orders = [row[0] for row in cursor.fetchall()]
    
    for order_id in orders:
        order_node = f"order_{order_id}"
        
        # Check if order has corresponding invoice and billing
        has_invoice = False
        has_billing = False
        
        try:
            for node in graph.successors(order_node):
                if 'billing' in str(node).lower() or 'invoice' in str(node).lower():
                    has_invoice = True
                    
            if not has_invoice:
                broken_flows.append({
                    'order_id': order_id,
                    'issue': 'Missing invoice/billing documents',
                    'severity': 'high'
                })
        except (nx.NetworkXError, StopIteration):
            broken_flows.append({
                'order_id': order_id,
                'issue': 'Disconnected from graph',
                'severity': 'critical'
            })
    
    return broken_flows

def traverse_graph_for_multihop_query(graph: nx.DiGraph, user_query: str, 
                                     db_conn: sqlite3.Connection) -> Tuple[Optional[List[Dict]], str]:
    """Attempt to resolve multi-hop query using graph traversal."""
    
    query_lower = user_query.lower()
    
    # Pattern: order → invoice → journal
    if any(x in query_lower for x in ['order', 'sales']) and \
       any(x in query_lower for x in ['journal', 'accounting', 'document']):
        result = graph_traverse_for_path(graph, 'sales_order', 'journal_entry')
        return result, "Graph traversal: Order → Invoice → Journal Entry"
    
    # Pattern: product → customer
    if 'product' in query_lower and 'customer' in query_lower:
        result = graph_traverse_for_path(graph, 'product', 'customer')
        return result, "Graph traversal: Product → Sales Order → Customer"
    
    # Pattern: broken/incomplete flows
    if 'broken' in query_lower or 'incomplete' in query_lower or 'incomplete flow' in query_lower:
        result = find_broken_flows(graph, db_conn)
        return result, "Graph analysis: Broken/incomplete O2C flows detected"
    
    return None, "No graph pattern matched"

# ============================================================================
# STREAMING RESPONSES (Optional)
# ============================================================================

async def generate_sql_streaming(
    user_query: str,
    table_schemas: Dict[str, List[str]]
):
    """Generate SQL with streaming."""
    
    schema_info = "Available tables:\n"
    for table in list(table_schemas.keys())[:10]:
        schema_info += f"  - {table}\n"
    
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT + "\n\n" + schema_info
        },
        {
            "role": "user",
            "content": f"Generate a SQL query for: {user_query}"
        }
    ]
    
    client = get_groq_client()
    with client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        stream=True,
        temperature=0.3,
        max_tokens=500,
    ) as response:
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
