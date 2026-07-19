import asyncio
import json
import logging
import os
import sys
import psycopg2
import nats

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_router import get_router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("KNOWLEDGE_GRAPH_SERVICE")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASSWORD", "SecurePassword_123!")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5433")

def get_db():
    return psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)

class KnowledgeGraphExtractor:
    def __init__(self):
        self.router = get_router()

    async def extract_knowledge(self, incident_text: str) -> dict:
        prompt = f"""
You are an IT Knowledge Graph Extractor v2.
Extract technical entities (e.g. Services, Servers, Networking, Databases) and their relationships from the incident text.
Return ONLY valid JSON exactly matching this schema:
{{
  "nodes": [
    {{"node_id": "service_name", "node_type": "Service", "properties": {{"description": "..."}}}}
  ],
  "edges": [
    {{
      "source_id": "service_name", 
      "target_id": "db_name", 
      "relationship": "depends_on", 
      "confidence": 0.9,
      "metadata": {{
        "source": "LLM_INFERENCE",
        "verified": false,
        "freshness": 1.0
      }}
    }}
  ]
}}

Incident Text:
{incident_text}
"""
        res = await self.router.execute_with_retry(90, prompt)
        if res.get("status") == "SUCCESS":
            try:
                cleaned = str(res.get("response", "")).strip()
                if cleaned.startswith("```"):
                    lines = cleaned.splitlines()
                    if lines[0].startswith("```"): lines = lines[1:]
                    if lines and lines[-1].startswith("```"): lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                
                return json.loads(cleaned)
            except Exception as e:
                logger.error(f"Failed to parse LLM KG extraction: {e}")
        return {"nodes": [], "edges": []}

    def persist_to_db(self, kg_data: dict):
        conn = get_db()
        try:
            with conn.cursor() as cur:
                for node in kg_data.get("nodes", []):
                    node_id = str(node.get("node_id")).lower().strip().replace(" ", "_")
                    node_type = str(node.get("node_type", "Unknown"))
                    props = node.get("properties", {})
                    
                    cur.execute("""
                        INSERT INTO knowledge_graph_nodes (node_id, node_type, properties)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (node_id) DO UPDATE SET
                            last_seen = NOW(),
                            properties = knowledge_graph_nodes.properties || EXCLUDED.properties
                    """, (node_id, node_type, json.dumps(props)))
                    
                # Setup metadata column if not exists
                try:
                    cur.execute("ALTER TABLE knowledge_graph_edges ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb")
                except Exception:
                    conn.rollback() # If it fails, ignore
                    
                for edge in kg_data.get("edges", []):
                    source = str(edge.get("source_id")).lower().strip().replace(" ", "_")
                    target = str(edge.get("target_id")).lower().strip().replace(" ", "_")
                    rel = str(edge.get("relationship", "related_to"))
                    conf = float(edge.get("confidence", 0.5))
                    meta = edge.get("metadata", {"source": "LLM", "verified": False, "freshness": 1.0})
                    
                    cur.execute("""
                        INSERT INTO knowledge_graph_edges (source_id, target_id, relationship, confidence, source_engine, metadata)
                        VALUES (%s, %s, %s, %s, 'LLM', %s)
                        ON CONFLICT (source_id, target_id, relationship) DO UPDATE SET
                            confidence = (knowledge_graph_edges.confidence + EXCLUDED.confidence) / 2,
                            metadata = knowledge_graph_edges.metadata || EXCLUDED.metadata
                    """, (source, target, rel, conf, json.dumps(meta)))
            conn.commit()
            logger.info(f"Persisted {len(kg_data.get('nodes', []))} nodes and {len(kg_data.get('edges', []))} edges to Knowledge Graph.")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to persist KG data to DB: {e}")
        finally:
            conn.close()

async def daemon():
    nc = await nats.connect(NATS_URL)
    logger.info(f"Connected to NATS at {NATS_URL} for Knowledge Graph Extraction.")
    extractor = KnowledgeGraphExtractor()

    async def extraction_handler(msg):
        try:
            req = json.loads(msg.data.decode())
            incident_text = req.get("incident_text", "")
            if incident_text:
                kg_data = await extractor.extract_knowledge(incident_text)
                if kg_data.get("nodes") or kg_data.get("edges"):
                    extractor.persist_to_db(kg_data)
        except Exception as e:
            logger.error(f"KG Extraction error: {e}")
            
    # Subscribe to incident resolutions for background KG building
    await nc.subscribe("ai.engine.knowledge_graph.extract", queue="kg-extraction-group", cb=extraction_handler)
    
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(daemon())
