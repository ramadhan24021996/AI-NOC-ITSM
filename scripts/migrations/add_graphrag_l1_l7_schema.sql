-- Migration: GraphRAG L1-L7 Enterprise Schema Expansion
-- Adds centrality scores, topology metadata, and graph embeddings columns to PostgreSQL

ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS pagerank_score FLOAT DEFAULT 0.0;
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS betweenness_score FLOAT DEFAULT 0.0;
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS closeness_score FLOAT DEFAULT 0.0;
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS topology_layer INT DEFAULT 7;
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS mac_address VARCHAR(64);
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS switch_port VARCHAR(128);
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS vlan_id VARCHAR(64);
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS bssid VARCHAR(64);
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS graph_embedding vector(128);

CREATE INDEX IF NOT EXISTS idx_kg_nodes_layer ON knowledge_graph_nodes(topology_layer);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_mac ON knowledge_graph_nodes(mac_address);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_vlan ON knowledge_graph_nodes(vlan_id);

CREATE TABLE IF NOT EXISTS knowledge_graph_topology_snapshots (
    id BIGSERIAL PRIMARY KEY,
    agent_id VARCHAR(255) NOT NULL,
    site_id VARCHAR(128) NOT NULL DEFAULT 'GLOBAL',
    topology_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kg_topo_agent ON knowledge_graph_topology_snapshots(agent_id);
