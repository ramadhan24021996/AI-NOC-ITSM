-- Sprint L: Live Log Incident Timeline
-- Adding comprehensive lifecycle timestamps and calculated durations to the incidents table

ALTER TABLE incidents
ADD COLUMN IF NOT EXISTS first_evidence_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS issue_started_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS ai_detection_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS correlation_completed_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS root_cause_completed_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS recommendation_generated_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS human_approval_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS execution_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS verification_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS solved_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS closed_time TIMESTAMP WITH TIME ZONE;

ALTER TABLE incidents
ADD COLUMN IF NOT EXISTS detection_duration_sec INTEGER,
ADD COLUMN IF NOT EXISTS analysis_duration_sec INTEGER,
ADD COLUMN IF NOT EXISTS approval_duration_sec INTEGER,
ADD COLUMN IF NOT EXISTS resolution_duration_sec INTEGER,
ADD COLUMN IF NOT EXISTS total_incident_duration_sec INTEGER;

-- Ensure default values for status and confidence if needed
ALTER TABLE incidents
ALTER COLUMN status SET DEFAULT 'Active';
