import json
import sqlite3
import datetime
import os

class ConversationContextManager:
    def __init__(self, db_path="cognitive_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS conversation_context (
                session_id TEXT PRIMARY KEY,
                active_device TEXT,
                active_incident TEXT,
                current_intent TEXT,
                previous_analysis TEXT,
                current_rca TEXT,
                current_recommendation TEXT,
                state TEXT,
                last_updated TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def get_context(self, session_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM conversation_context WHERE session_id = ?', (session_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return {
                "session_id": row[0],
                "active_device": row[1],
                "active_incident": row[2],
                "current_intent": row[3],
                "previous_analysis": row[4],
                "current_rca": row[5],
                "current_recommendation": row[6],
                "state": row[7],
                "last_updated": row[8]
            }
        return self._create_default_context(session_id)

    def _create_default_context(self, session_id):
        return {
            "session_id": session_id,
            "active_device": None,
            "active_incident": None,
            "current_intent": None,
            "previous_analysis": None,
            "current_rca": None,
            "current_recommendation": None,
            "state": "IDLE",
            "last_updated": datetime.datetime.now().isoformat()
        }

    def update_context(self, session_id, **kwargs):
        context = self.get_context(session_id)
        
        for key, value in kwargs.items():
            if key in context:
                context[key] = value
                
        context["last_updated"] = datetime.datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO conversation_context 
            (session_id, active_device, active_incident, current_intent, previous_analysis, current_rca, current_recommendation, state, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            context["session_id"],
            context["active_device"],
            context["active_incident"],
            context["current_intent"],
            context["previous_analysis"],
            context["current_rca"],
            context["current_recommendation"],
            context["state"],
            context["last_updated"]
        ))
        conn.commit()
        conn.close()
        return context

    def resolve_pronouns(self, session_id, user_query):
        """
        Resolves pronouns like 'nya' or 'itu' to the active device/incident in context.
        Example: "Apa penyebabnya?" -> "Apa penyebab dari PC-TMS?"
        """
        context = self.get_context(session_id)
        resolved_query = user_query.lower()
        
        if "nya" in resolved_query or "itu" in resolved_query:
            if context["active_device"]:
                resolved_query = resolved_query.replace("nya", f" dari {context['active_device']}")
                resolved_query = resolved_query.replace("itu", f" {context['active_device']}")
            elif context["active_incident"]:
                resolved_query = resolved_query.replace("nya", f" dari insiden {context['active_incident']}")
                
        return resolved_query
