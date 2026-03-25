import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, AsyncGenerator
import pandas as pd
import networkx as nx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    try:
        # Use the data path from environment or default
        data_path = os.getenv('DATA_PATH', './sap-o2c-data')
        global_state.data_path = data_path
        
        # Load data
        df_dict = load_jsonl_files(data_path)
        
        # Create database
        conn = create_sqlite_db(df_dict)
        global_state.db_connection = conn
        
        # Build graph
        G = build_graph(df_dict, conn)
        global_state.graph = G
        
        # Store table schemas
        for table_name in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall():
            table_name = table_name[0]
            global_state.table_schemas[table_name] = get_table_schema(conn, table_name)
        
        print("System initialized successfully!")
        
    except Exception as e:
        print(f"Error during startup: {e}")
        raise
    
    yield
    
    # Shutdown
    if global_state.db_connection:
        global_state.db_connection.close()
        print("Database connection closed")

app = FastAPI(title="O2C Graph Query System", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
class GlobalState:
    def __init__(self):
        self.db_connection: Optional[sqlite3.Connection] = None
        self.graph: Optional[nx.DiGraph] = None
        self.entities: Dict[str, Dict] = {}
        self.table_schemas: Dict[str, List[str]] = {}
        self.data_path: Path = None
        
global_state = GlobalState()

# Pydantic models
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    user_query: str
    messages: Optional[List[ChatMessage]] = None  # Optional for backwards compatibility

class ChatResponse(BaseModel):
    response: str
    referenced_nodes: List[str]
    query_type: str
    structured_response: Optional[Dict[str, Any]] = None  # New: structured format for frontend
    referenced_entities: Optional[Dict[str, Any]] = None  # New: full entity details with relationships

# ============================================================================
# DATA LOADING
# ============================================================================

def load_jsonl_files(data_path: str) -> Dict[str, pd.DataFrame]:
    """Load all JSONL files from the data directory."""
    print(f"Loading JSONL data from {data_path}...")
    
    data_frames = {}
    data_dir = Path(data_path)
    
    if not data_dir.exists():
        raise ValueError(f"Data directory not found: {data_path}")
    
    # Scan all subdirectories for JSONL files
    for entity_dir in sorted(data_dir.iterdir()):
        if not entity_dir.is_dir():
            continue
        
        entity_name = entity_dir.name
        jsonl_files = list(entity_dir.glob("*.jsonl"))
        
        if not jsonl_files:
            continue
        
        print(f"  Loading {entity_name}...")
        
        # Load and concatenate all JSONL files for this entity
        dfs = []
        for jsonl_file in jsonl_files:
            try:
                df = pd.read_json(jsonl_file, lines=True)
                dfs.append(df)
            except Exception as e:
                print(f"    Warning: Error loading {jsonl_file}: {e}")
        
        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            data_frames[entity_name] = combined_df
            print(f"    Loaded {len(combined_df)} rows")
    
    print(f"Total entities loaded: {len(data_frames)}")
    return data_frames

def create_sqlite_db(data_frames: Dict[str, pd.DataFrame]) -> sqlite3.Connection:
    """Create in-memory SQLite database from dataframes."""
    print("Creating in-memory SQLite database...")
    
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Create tables
    for entity_name, df in data_frames.items():
        print(f"  Creating table: {entity_name}")
        
        # Replace problematic characters in column names
        df.columns = df.columns.str.replace(" ", "_").str.lower()
        
        # Convert nested objects (dicts, lists) to JSON strings
        for col in df.columns:
            if df[col].dtype == 'object':
                # Check if this column contains dicts or lists
                sample_values = df[col].dropna().head(1)
                if len(sample_values) > 0:
                    sample_val = sample_values.iloc[0]
                    if isinstance(sample_val, (dict, list)):
                        # Convert to JSON string
                        df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
        
        # Create table and insert data
        df.to_sql(entity_name, conn, if_exists='replace', index=False)
    
    print("Database created successfully")
    return conn

def get_table_schema(conn: sqlite3.Connection, table_name: str) -> List[str]:
    """Get column names for a table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def build_graph(df_dict: Dict[str, pd.DataFrame], conn: sqlite3.Connection) -> nx.DiGraph:
    """Build a directed graph from the O2C data."""
    print("Building graph...")
    
    G = nx.DiGraph()
    G.graph['description'] = 'Order-to-Cash Process Graph'
    
    # Helper function to add nodes from a dataframe
    def add_nodes_from_df(entity_type: str, df: pd.DataFrame, id_col: str):
        """Add entity nodes to graph."""
        for _, row in df.iterrows():
            node_id = f"{entity_type}:{row[id_col]}"
            node_attrs = {
                'type': entity_type,
                'entity_id': str(row[id_col]),
            }
            # Add all non-null attributes
            for col in df.columns:
                if pd.notna(row[col]):
                    node_attrs[col] = str(row[col]) if not isinstance(row[col], (int, float, bool)) else row[col]
            
            G.add_node(node_id, **node_attrs)
    
    # Add entity nodes
    print("  Adding entity nodes...")
    
    if 'sales_order_headers' in df_dict:
        add_nodes_from_df('SalesOrder', df_dict['sales_order_headers'], 'salesorder')
    
    if 'sales_order_items' in df_dict:
        add_nodes_from_df('SalesOrderItem', df_dict['sales_order_items'], 'salesorder')
    
    if 'outbound_delivery_headers' in df_dict:
        add_nodes_from_df('Delivery', df_dict['outbound_delivery_headers'], 'deliverydocument')
    
    if 'outbound_delivery_items' in df_dict:
        add_nodes_from_df('DeliveryItem', df_dict['outbound_delivery_items'], 'deliverydocument')
    
    if 'billing_document_headers' in df_dict:
        add_nodes_from_df('Invoice', df_dict['billing_document_headers'], 'billingdocument')
    
    if 'billing_document_items' in df_dict:
        add_nodes_from_df('InvoiceItem', df_dict['billing_document_items'], 'billingdocument')
    
    if 'journal_entry_items_accounts_receivable' in df_dict:
        add_nodes_from_df('JournalEntry', df_dict['journal_entry_items_accounts_receivable'], 'accountingdocument')
    
    if 'payments_accounts_receivable' in df_dict:
        add_nodes_from_df('Payment', df_dict['payments_accounts_receivable'], 'accountingdocument')
    
    if 'business_partners' in df_dict:
        add_nodes_from_df('Customer', df_dict['business_partners'], 'businesspartner')
    
    if 'products' in df_dict:
        add_nodes_from_df('Product', df_dict['products'], 'product')
    
    if 'plants' in df_dict:
        add_nodes_from_df('Plant', df_dict['plants'], 'plant')
    
    # Add relationships
    print("  Adding relationships...")
    
    # SalesOrder → Customer
    if 'sales_order_headers' in df_dict:
        for _, row in df_dict['sales_order_headers'].iterrows():
            try:
                so_id = f"SalesOrder:{row['salesorder']}"
                cust_id = f"Customer:{row['soldtoparty']}"
                if G.has_node(so_id) and G.has_node(cust_id):
                    G.add_edge(so_id, cust_id, relationship='ordered_by')
            except:
                pass
    
    # SalesOrder → SalesOrderItem
    if 'sales_order_items' in df_dict:
        for _, row in df_dict['sales_order_items'].iterrows():
            try:
                so_id = f"SalesOrder:{row['salesorder']}"
                soi_id = f"SalesOrderItem:{row['salesorder']}"
                if G.has_node(so_id) and G.has_node(soi_id):
                    G.add_edge(so_id, soi_id, relationship='contains_item')
            except:
                pass
    
    # SalesOrderItem → Product
    if 'sales_order_items' in df_dict:
        for _, row in df_dict['sales_order_items'].iterrows():
            try:
                soi_id = f"SalesOrderItem:{row['salesorder']}"
                prod_id = f"Product:{row['material']}"
                if G.has_node(soi_id) and G.has_node(prod_id):
                    G.add_edge(soi_id, prod_id, relationship='references_product')
            except:
                pass
    
    # SalesOrderItem → Plant
    if 'sales_order_items' in df_dict:
        for _, row in df_dict['sales_order_items'].iterrows():
            try:
                soi_id = f"SalesOrderItem:{row['salesorder']}"
                plant_id = f"Plant:{row['productionplant']}"
                if G.has_node(soi_id) and G.has_node(plant_id):
                    G.add_edge(soi_id, plant_id, relationship='produced_at')
            except:
                pass
    
    # DeliveryItem → SalesOrderItem (via referenceSdDocument)
    if 'outbound_delivery_items' in df_dict:
        for _, row in df_dict['outbound_delivery_items'].iterrows():
            try:
                if pd.notna(row.get('referencesd document')):
                    di_id = f"DeliveryItem:{row['deliverydocument']}"
                    soi_id = f"SalesOrderItem:{row['referencesd document']}"
                    if G.has_node(di_id) and G.has_node(soi_id):
                        G.add_edge(di_id, soi_id, relationship='fulfills')
            except:
                pass
    
    # Delivery → DeliveryItem
    if 'outbound_delivery_items' in df_dict:
        for _, row in df_dict['outbound_delivery_items'].iterrows():
            try:
                d_id = f"Delivery:{row['deliverydocument']}"
                di_id = f"DeliveryItem:{row['deliverydocument']}"
                if G.has_node(d_id) and G.has_node(di_id):
                    G.add_edge(d_id, di_id, relationship='contains_item')
            except:
                pass
    
    # Invoice → InvoiceItem
    if 'billing_document_items' in df_dict:
        for _, row in df_dict['billing_document_items'].iterrows():
            try:
                inv_id = f"Invoice:{row['billingdocument']}"
                ii_id = f"InvoiceItem:{row['billingdocument']}"
                if G.has_node(inv_id) and G.has_node(ii_id):
                    G.add_edge(inv_id, ii_id, relationship='contains_item')
            except:
                pass
    
    # Invoice → Customer
    if 'billing_document_headers' in df_dict:
        for _, row in df_dict['billing_document_headers'].iterrows():
            try:
                inv_id = f"Invoice:{row['billingdocument']}"
                cust_id = f"Customer:{row['soldtoparty']}"
                if G.has_node(inv_id) and G.has_node(cust_id):
                    G.add_edge(inv_id, cust_id, relationship='billed_to')
            except:
                pass
    
    # Invoice → JournalEntry
    if 'billing_document_headers' in df_dict:
        for _, row in df_dict['billing_document_headers'].iterrows():
            try:
                inv_id = f"Invoice:{row['billingdocument']}"
                je_id = f"JournalEntry:{row['accountingdocument']}"
                if G.has_node(inv_id) and G.has_node(je_id):
                    G.add_edge(inv_id, je_id, relationship='posted_as')
            except:
                pass
    
    print(f"  Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G

# ============================================================================
# REST ENDPOINTS
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "graph_nodes": global_state.graph.number_of_nodes() if global_state.graph else 0,
        "graph_edges": global_state.graph.number_of_edges() if global_state.graph else 0,
    }

@app.get("/graph")
async def get_graph():
    """Return graph data for visualization."""
    if not global_state.graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")
    
    nodes = []
    edges = []
    
    for node_id, attrs in global_state.graph.nodes(data=True):
        nodes.append({
            "id": node_id,
            "type": attrs.get('type', 'Unknown'),
            "label": f"{attrs.get('type', '')}:{attrs.get('entity_id', '')}",
            "size": 20,
        })
    
    for source, target, attrs in global_state.graph.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            "relationship": attrs.get('relationship', 'related_to'),
        })
    
    return {"nodes": nodes, "edges": edges}

@app.get("/graph/entity/{entity_type}/{entity_id}")
async def get_entity_details(entity_type: str, entity_id: str):
    """Get details for a specific entity."""
    if not global_state.graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")
    
    node_id = f"{entity_type}:{entity_id}"
    if not global_state.graph.has_node(node_id):
        raise HTTPException(status_code=404, detail="Entity not found")
    
    attrs = global_state.graph.nodes[node_id]
    
    # Get connected nodes
    predecessors = list(global_state.graph.predecessors(node_id))
    successors = list(global_state.graph.successors(node_id))
    
    return {
        "id": node_id,
        "attributes": attrs,
        "connected_to": {
            "predecessors": predecessors,
            "successors": successors,
        }
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    """Chat endpoint for natural language queries with fallback strategies."""
    if not global_state.db_connection:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    user_query = request.user_query
    
    # Import LLM utilities
    from llm_utils import (
        generate_sql_from_query, execute_query_safely, synthesize_response,
        is_query_in_scope, detect_query_requires_graph, traverse_graph_for_multihop_query,
        create_structured_response, fetch_entity_details_with_relationships
    )
    
    try:
        # Step 1: Check if query is in scope
        if not is_query_in_scope(user_query):
            return ChatResponse(
                response="I'm designed to answer questions about the Order-to-Cash process, including orders, deliveries, billing, payments, customers, and products. Please ask about topics related to your O2C data.",
                referenced_nodes=[],
                query_type="out_of_scope"
            )
        
        # Step 2: Check if query requires graph traversal (multi-hop)
        if detect_query_requires_graph(user_query):
            print(f"Query detected as multi-hop, attempting graph traversal: {user_query}")
            graph_results, graph_method = traverse_graph_for_multihop_query(
                global_state.graph,
                user_query,
                global_state.db_connection
            )
            
            if graph_results is not None and len(graph_results) > 0:
                # Synthesize graph results with structured format
                response_text, referenced_nodes = await synthesize_response(
                    user_query,
                    graph_method,
                    graph_results,
                    global_state.graph
                )
                
                # Also create structured version
                structured_resp = await create_structured_response(
                    user_query,
                    graph_method,
                    graph_results,
                    global_state.graph
                )
                
                # Fetch full entity details with relationships
                entity_details = await fetch_entity_details_with_relationships(
                    referenced_nodes,
                    global_state.graph
                )
                
                return ChatResponse(
                    response=response_text,
                    referenced_nodes=referenced_nodes,
                    query_type="graph_traversal",
                    structured_response=structured_resp,
                    referenced_entities=entity_details
                )
        
        # Step 3: Try SQL-based query generation
        print(f"Processing query with LLM: {user_query}")
        
        try:
            sql_query = await generate_sql_from_query(
                user_query,
                global_state.table_schemas,
                global_state.db_connection
            )
            
            print(f"Generated SQL: {sql_query}")
            
            # Execute query safely
            results = execute_query_safely(global_state.db_connection, sql_query)
            
            print(f"Query returned {len(results)} results")
            
            # Synthesize response using LLM
            response_text, referenced_nodes = await synthesize_response(
                user_query,
                sql_query,
                results,
                global_state.graph
            )
            
            # Create structured response
            structured_resp = await create_structured_response(
                user_query,
                sql_query,
                results,
                global_state.graph
            )
            
            # Fetch full entity details with relationships
            entity_details = await fetch_entity_details_with_relationships(
                referenced_nodes,
                global_state.graph
            )
            
            return ChatResponse(
                response=response_text,
                referenced_nodes=referenced_nodes,
                query_type="sql",
                structured_response=structured_resp,
                referenced_entities=entity_details
            )
        
        except Exception as sql_error:
            print(f"SQL query failed: {sql_error}")
            
            # Fallback: Try graph traversal as last resort for any query
            if global_state.graph:
                print("Falling back to graph traversal for broader results")
                # Try generic multi-hop detection
                graph_results, graph_method = traverse_graph_for_multihop_query(
                    global_state.graph,
                    user_query,
                    global_state.db_connection
                )
                
                if graph_results is not None and len(graph_results) > 0:
                    response_text, referenced_nodes = await synthesize_response(
                        user_query,
                        f"Graph Analysis via: {graph_method}",
                        graph_results,
                        global_state.graph
                    )
                    
                    # Create structured response
                    structured_resp = await create_structured_response(
                        user_query,
                        f"Graph Analysis via: {graph_method}",
                        graph_results,
                        global_state.graph
                    )
                    
                    # Fetch full entity details with relationships
                    entity_details = await fetch_entity_details_with_relationships(
                        referenced_nodes,
                        global_state.graph
                    )
                    
                    return ChatResponse(
                        response=response_text,
                        referenced_nodes=referenced_nodes,
                        query_type="graph_fallback",
                        structured_response=structured_resp,
                        referenced_entities=entity_details
                    )
            
            # If graph fallback also fails, return user-friendly error instead of 500
            print(f"All query methods failed, returning graceful error")
            return ChatResponse(
                response=f"I encountered an issue processing your query. The system couldn't generate proper SQL or find results through graph analysis. Please try rephrasing your question or try a simpler query.",
                referenced_nodes=[],
                query_type="error"
            )
    
    except Exception as e:
        print(f"Error processing query: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

@app.get("/schema")
async def get_schema():
    """Get database schema information for debugging."""
    if not global_state.db_connection:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    schema_info = {}
    cursor = global_state.db_connection.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    for (table_name,) in tables:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [{"name": row[1], "type": row[2]} for row in cursor.fetchall()]
        
        # Get sample data
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
        sample = None
        if cursor.description:
            col_names = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            if row:
                sample = dict(zip(col_names, row))
        
        schema_info[table_name] = {
            "columns": columns,
            "sample": sample
        }
    
    return schema_info

@app.get("/")
async def root():
    """Serve the frontend."""
    return FileResponse("frontend/index.html", media_type="text/html")

# Serve static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

if __name__ == "__main__":
    import uvicorn
    # Use environment variables from .env file
    port = int(os.getenv('PORT', 5555))
    host = os.getenv('HOST', '127.0.0.1')
    print(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
