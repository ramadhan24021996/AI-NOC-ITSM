-- 02-performance-indexes.sql
-- Enterprise High-Throughput Indexing for Level-5 AI NOC Platform
CREATE INDEX IF NOT EXISTS idx_incidents_flag_timestamp ON public.incidents (flag, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_trace_id ON public.incidents (trace_id);
CREATE INDEX IF NOT EXISTS idx_incidents_layer ON public.incidents (layer);
