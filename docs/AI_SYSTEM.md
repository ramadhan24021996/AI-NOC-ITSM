# AI System

## Models
- **Primary:** Google Gemini (gemini-1.5-flash/pro)
- **Fallbacks:** Groq (llama3-70b-8192), DeepSeek (deepseek-chat)
- **Embeddings:** Google embedding-001 (768 dimensions)

## Key Engines
1. **Consensus Engine:** Runs multi-LLM debates to arrive at a recommended action.
2. **Critic Engine:** Plays devil's advocate, attempting to find flaws in the consensus.
3. **RAG Engine:** Retrieves similar past incidents from PostgreSQL using cosine similarity.
4. **Intent Classifier:** Non-LLM ML model (TF-IDF) for fast initial classification and routing.
5. **Policy Engine:** Rule-based (OPA-style) validation of AI decisions.
