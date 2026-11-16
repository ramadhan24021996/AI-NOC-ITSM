package incident

// Evidence Explorer — Audit Jejak Bukti & Readiness AI Engine
//
// Every value returned by this module is derived from live database records.
// No synthetic / placeholder KPI is emitted: when a data source is empty, the
// response explicitly reports "NO DATA" so operators are never misled.
//
// Governance Rule #6 (Dual-Evidence Binding) is evaluated per incident using
// the same criteria as GuardTransition (state_machine.go):
//   execution_evidence  : EXECUTION_EVIDENCE | AUTO_MITIGATE | ACTION_EXECUTED
//   post_remediation    : POST_REMEDIATION_EVIDENCE | VERIFICATION_SUCCESS
//   valid binding       : T_post >= T_exec on the same incident_id
//   alternative proof   : autonomous_decision_records.verification_result = 'PASSED'

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

const (
	evStatusPass     = "PASS"
	evStatusConflict = "CONFLICT"
	evStatusStale    = "STALE"
	evStatusDup      = "DUPLICATE"
	evStatusNeedMore = "NEED MORE"
	evStatusRejected = "REJECTED"

	evStatsWindow        = 24 * time.Hour
	evTelemetryFreshness = 15 * time.Minute
	evCollectorWarnAfter = 2 * time.Minute
	evCollectorErrAfter  = 5 * time.Minute
)

var execEvidenceTypes = []string{"EXECUTION_EVIDENCE", "AUTO_MITIGATE", "ACTION_EXECUTED"}
var postEvidenceTypes = []string{"POST_REMEDIATION_EVIDENCE", "VERIFICATION_SUCCESS"}

type evidenceCollector struct {
	Name        string  `json:"name"`
	Status      string  `json:"status"`
	SuccessRate float64 `json:"success_rate"`
	LastSeen    string  `json:"last_seen"`
	Detail      string  `json:"detail"`
}

type evidenceLogItem struct {
	TraceID        string    `json:"trace_id"`
	IncidentID     string    `json:"incident_id"`
	Source         string    `json:"source"`
	Host           string    `json:"host"`
	Status         string    `json:"status"`
	DecisionReason string    `json:"decision_reason"`
	Quality        float64   `json:"quality"`
	Confidence     float64   `json:"confidence"`
	Age            string    `json:"age"`
	ObservedAt     time.Time `json:"observed_at"`
	dedupKey       string
}

type rule6State struct {
	ExecAt         *time.Time `json:"exec_at"`
	PostAt         *time.Time `json:"post_at"`
	Bound          bool       `json:"bound"`
	DecisionPassed bool       `json:"decision_passed"`
	Verdict        string     `json:"verdict"`
}

func (r rule6State) satisfied() bool { return r.Bound || r.DecisionPassed }

func evHumanAge(t time.Time) string {
	if t.IsZero() {
		return "—"
	}
	secs := int(time.Since(t).Seconds())
	if secs < 0 {
		secs = 0
	}
	switch {
	case secs < 60:
		return fmt.Sprintf("%d detik", secs)
	case secs < 3600:
		return fmt.Sprintf("%d menit", secs/60)
	case secs < 86400:
		return fmt.Sprintf("%d jam", secs/3600)
	default:
		return fmt.Sprintf("%d hari", secs/86400)
	}
}

func evNormalizeConfidence(v float64) float64 {
	if v > 0 && v <= 1.0 {
		return v * 100.0
	}
	return v
}

func evPct(n, total int) string {
	if total == 0 {
		return "—"
	}
	return fmt.Sprintf("%.1f%%", float64(n)*100.0/float64(total))
}

var osiLayerNames = map[int]string{
	1: "L1 Physical", 2: "L2 Data Link", 3: "L3 Network", 4: "L4 Transport",
	5: "L5 Session", 6: "L6 Presentation", 7: "L7 Application",
}

// loadRule6States evaluates Rule #6 dual-evidence binding for every incident that
// has evidence events, plus autonomous decision verification records.
func (h *Handler) loadRule6States() map[string]*rule6State {
	states := make(map[string]*rule6State)
	type row struct {
		IncidentID string     `gorm:"column:incident_id"`
		ExecAt     *time.Time `gorm:"column:exec_at"`
		PostAt     *time.Time `gorm:"column:post_at"`
	}
	var rows []row
	h.db.Raw(`
		SELECT incident_id,
		       MIN(created_at) FILTER (WHERE event_type IN ?) AS exec_at,
		       MAX(created_at) FILTER (WHERE event_type IN ?) AS post_at
		FROM incident_events
		GROUP BY incident_id
	`, execEvidenceTypes, postEvidenceTypes).Scan(&rows)
	for _, r := range rows {
		st := &rule6State{ExecAt: r.ExecAt, PostAt: r.PostAt}
		st.Bound = r.ExecAt != nil && r.PostAt != nil && !r.PostAt.Before(*r.ExecAt)
		states[r.IncidentID] = st
	}

	var passed []string
	h.db.Raw(`SELECT DISTINCT incident_id::text FROM autonomous_decision_records WHERE verification_result = 'PASSED'`).Scan(&passed)
	for _, id := range passed {
		st, ok := states[id]
		if !ok {
			st = &rule6State{}
			states[id] = st
		}
		st.DecisionPassed = true
	}

	for _, st := range states {
		switch {
		case st.Bound:
			st.Verdict = "DUAL-EVIDENCE BOUND (T_post ≥ T_exec)"
		case st.DecisionPassed:
			st.Verdict = "VERIFIED via autonomous_decision_records (PASSED)"
		case st.ExecAt != nil && st.PostAt == nil:
			st.Verdict = "AWAITING post_remediation_evidence"
		case st.ExecAt == nil && st.PostAt != nil:
			st.Verdict = "INVALID: post_remediation_evidence tanpa execution_evidence"
		case st.ExecAt != nil && st.PostAt != nil:
			st.Verdict = "INVALID: T_post < T_exec"
		default:
			st.Verdict = "NO REMEDIATION EVIDENCE"
		}
	}
	return states
}

func (h *Handler) loadEvidenceCollectors() []evidenceCollector {
	collectors := []evidenceCollector{}

	// 1. Fleet endpoint agents (Windows / Linux)
	type fleetAgg struct {
		Total    int        `gorm:"column:total"`
		Online   int        `gorm:"column:online"`
		LastSeen *time.Time `gorm:"column:last_seen"`
	}
	var fa fleetAgg
	h.db.Raw(`
		SELECT COUNT(*) AS total,
		       COUNT(*) FILTER (WHERE last_seen >= NOW() - INTERVAL '2 minutes') AS online,
		       MAX(last_seen) AS last_seen
		FROM fleet_devices
	`).Scan(&fa)
	collectors = append(collectors, evCollectorFromRatio("Fleet Endpoint Agents", fa.Online, fa.Total, fa.LastSeen,
		fmt.Sprintf("%d/%d agent melapor < 2 menit", fa.Online, fa.Total)))

	// 2. Canonical telemetry ingestion (telemetry_logs)
	type telAgg struct {
		Reporting int        `gorm:"column:reporting"`
		LastSeen  *time.Time `gorm:"column:last_seen"`
	}
	var ta telAgg
	h.db.Raw(`
		SELECT COUNT(DISTINCT device_name) AS reporting, MAX(timestamp) AS last_seen
		FROM telemetry_logs
		WHERE timestamp >= NOW() - INTERVAL '15 minutes'
	`).Scan(&ta)
	var totalDevices int
	h.db.Raw(`SELECT COUNT(*) FROM devices`).Scan(&totalDevices)
	if ta.LastSeen == nil {
		h.db.Raw(`SELECT MAX(timestamp) FROM telemetry_logs WHERE timestamp >= NOW() - INTERVAL '1 day'`).Scan(&ta.LastSeen)
	}
	collectors = append(collectors, evCollectorFromRatio("Telemetry Ingestion (telemetry_logs)", ta.Reporting, totalDevices, ta.LastSeen,
		fmt.Sprintf("%d/%d device mengirim metrik < 15 menit", ta.Reporting, totalDevices)))

	// 3. Hardware & Enterprise collectors (system_telemetry_events)
	type steAgg struct {
		Total    int        `gorm:"column:total"`
		Healthy  int        `gorm:"column:healthy"`
		LastSeen *time.Time `gorm:"column:last_seen"`
	}
	var sa steAgg
	h.db.Raw(`
		SELECT COUNT(*) AS total,
		       COUNT(*) FILTER (WHERE UPPER(status) NOT IN ('ERROR', 'CRITICAL', 'FAILED')) AS healthy,
		       MAX(created_at) AS last_seen
		FROM system_telemetry_events
		WHERE created_at >= NOW() - INTERVAL '1 hour'
	`).Scan(&sa)
	collectors = append(collectors, evCollectorFromRatio("Hardware & Enterprise Collector", sa.Healthy, sa.Total, sa.LastSeen,
		fmt.Sprintf("%d/%d sweep sehat (1 jam)", sa.Healthy, sa.Total)))

	// 4. AI agent heartbeats (staleness always wins over self-reported status)
	type hbRow struct {
		Agent    string    `gorm:"column:agent"`
		Status   string    `gorm:"column:status"`
		LastSeen time.Time `gorm:"column:last_seen"`
	}
	var hbs []hbRow
	h.db.Raw(`SELECT agent, status, last_seen FROM agent_heartbeats ORDER BY agent`).Scan(&hbs)
	for _, hb := range hbs {
		age := time.Since(hb.LastSeen)
		status := "Healthy"
		rate := 100.0
		switch {
		case age > evCollectorErrAfter:
			status, rate = "Error", 0.0
		case age > evCollectorWarnAfter:
			status, rate = "Warning", 50.0
		case strings.ToUpper(hb.Status) != "ONLINE":
			status, rate = "Warning", 50.0
		}
		collectors = append(collectors, evidenceCollector{
			Name:        "AI Agent: " + hb.Agent,
			Status:      status,
			SuccessRate: rate,
			LastSeen:    evHumanAge(hb.LastSeen),
			Detail:      "self-reported: " + hb.Status,
		})
	}
	return collectors
}

func evCollectorFromRatio(name string, ok, total int, lastSeen *time.Time, detail string) evidenceCollector {
	c := evidenceCollector{Name: name, Detail: detail, LastSeen: "—"}
	if lastSeen != nil {
		c.LastSeen = evHumanAge(*lastSeen)
	}
	if total == 0 {
		c.Status = "No Data"
		return c
	}
	c.SuccessRate = float64(ok) * 100.0 / float64(total)
	switch {
	case lastSeen == nil || time.Since(*lastSeen) > evCollectorErrAfter*3:
		c.Status = "Error"
	case c.SuccessRate >= 90:
		c.Status = "Healthy"
	case c.SuccessRate >= 60:
		c.Status = "Warning"
	default:
		c.Status = "Error"
	}
	return c
}

// GetEvidenceExplorer — GET /api/evidence_explorer
func (h *Handler) GetEvidenceExplorer(c *gin.Context) {
	if h.db == nil {
		c.JSON(http.StatusOK, gin.H{
			"readiness":  gin.H{"status": "NO EVIDENCE DATA", "level": "none", "reason": "Database tidak terhubung — Evidence Engine tidak dapat menilai readiness.", "quality": "—", "confidence": "—", "conflicts": 0, "missing": 0},
			"stats":      gin.H{"validated_pct": "—", "conflict_pct": "—", "need_more_pct": "—", "rejected_pct": "—", "osi_distribution": []string{}, "pipeline": gin.H{}},
			"collectors": []evidenceCollector{},
			"graph":      gin.H{"nodes": []gin.H{}, "edges": []gin.H{}},
			"logs":       []evidenceLogItem{},
		})
		return
	}

	rule6 := h.loadRule6States()

	// Fresh telemetry per device (for STALE detection)
	type telRow struct {
		DeviceName string    `gorm:"column:device_name"`
		LastTs     time.Time `gorm:"column:last_ts"`
	}
	var telRows []telRow
	h.db.Raw(`SELECT device_name, MAX(timestamp) AS last_ts FROM telemetry_logs WHERE timestamp >= NOW() - INTERVAL '1 day' GROUP BY device_name`).Scan(&telRows)
	lastTelemetry := make(map[string]time.Time, len(telRows))
	for _, t := range telRows {
		lastTelemetry[t.DeviceName] = t.LastTs
	}

	logs := []evidenceLogItem{}

	// A. Rule #6 evidence events (incident_events)
	type evRow struct {
		EventID    int       `gorm:"column:event_id"`
		IncidentID string    `gorm:"column:incident_id"`
		EventType  string    `gorm:"column:event_type"`
		Host       string    `gorm:"column:host"`
		Conf       float64   `gorm:"column:conf"`
		CreatedAt  time.Time `gorm:"column:created_at"`
	}
	var evRows []evRow
	h.db.Raw(`
		SELECT e.event_id, e.incident_id, e.event_type,
		       COALESCE(NULLIF(e.payload->>'target_asset', ''), NULLIF(e.payload->>'pc_name', ''), i.device_name, '') AS host,
		       COALESCE(NULLIF(e.payload->>'verification_confidence', '')::float, i.confidence, 0) AS conf,
		       e.created_at
		FROM incident_events e
		LEFT JOIN incidents i ON i.incident_id::text = e.incident_id
		WHERE e.event_type IN ?
		ORDER BY e.created_at DESC
		LIMIT 25
	`, append(append([]string{}, execEvidenceTypes...), postEvidenceTypes...)).Scan(&evRows)
	for _, e := range evRows {
		st := rule6[e.IncidentID]
		if st == nil {
			st = &rule6State{Verdict: "NO REMEDIATION EVIDENCE"}
		}
		isPost := false
		for _, t := range postEvidenceTypes {
			if t == e.EventType {
				isPost = true
			}
		}
		item := evidenceLogItem{
			TraceID:    fmt.Sprintf("EVT-%d", e.EventID),
			IncidentID: e.IncidentID,
			Source:     "incident_events · " + e.EventType,
			Host:       e.Host,
			Confidence: evNormalizeConfidence(e.Conf),
			ObservedAt: e.CreatedAt,
		}
		switch {
		case st.Bound:
			item.Status, item.Quality = evStatusPass, 100
		case isPost:
			item.Status, item.Quality = evStatusConflict, 30
		default:
			item.Status, item.Quality = evStatusNeedMore, 60
		}
		item.DecisionReason = "Rule #6: " + st.Verdict
		logs = append(logs, item)
	}

	// B. AI evidence quality scoring (ai_evidence_quality, optional table)
	type qRow struct {
		IncidentID   string    `gorm:"column:incident_id"`
		MetricsScore float64   `gorm:"column:metrics_score"`
		LogsScore    float64   `gorm:"column:logs_score"`
		TopoScore    float64   `gorm:"column:topology_score"`
		OverallScore float64   `gorm:"column:overall_score"`
		Host         string    `gorm:"column:host"`
		Conf         float64   `gorm:"column:conf"`
		EvaluatedAt  time.Time `gorm:"column:evaluated_at"`
	}
	var qRows []qRow
	h.db.Raw(`
		SELECT q.incident_id, COALESCE(q.metrics_score, 0) AS metrics_score, COALESCE(q.logs_score, 0) AS logs_score,
		       COALESCE(q.topology_score, 0) AS topology_score, COALESCE(q.overall_score, 0) AS overall_score,
		       COALESCE(i.device_name, '') AS host, COALESCE(i.confidence, q.overall_score, 0) AS conf, q.evaluated_at
		FROM ai_evidence_quality q
		LEFT JOIN incidents i ON i.incident_id::text = q.incident_id
		ORDER BY q.evaluated_at DESC
		LIMIT 15
	`).Scan(&qRows)
	for _, q := range qRows {
		status := evStatusPass
		switch {
		case q.OverallScore < 0.5:
			status = evStatusRejected
		case q.OverallScore < 0.7:
			status = evStatusNeedMore
		}
		logs = append(logs, evidenceLogItem{
			TraceID:        "EQ-" + q.IncidentID,
			IncidentID:     q.IncidentID,
			Source:         "ai_evidence_quality",
			Host:           q.Host,
			Status:         status,
			DecisionReason: fmt.Sprintf("Skor evidence %.2f (metrics %.2f · logs %.2f · topology %.2f)", q.OverallScore, q.MetricsScore, q.LogsScore, q.TopoScore),
			Quality:        q.OverallScore * 100,
			Confidence:     evNormalizeConfidence(q.Conf),
			ObservedAt:     q.EvaluatedAt,
		})
	}

	// C. Incident anomaly evidence (incidents)
	type incRow struct {
		IncidentID  int       `gorm:"column:incident_id"`
		DeviceName  string    `gorm:"column:device_name"`
		Flag        string    `gorm:"column:flag"`
		Evidence    string    `gorm:"column:evidence"`
		HasRaw      bool      `gorm:"column:has_raw"`
		Confidence  float64   `gorm:"column:confidence"`
		Layer       int       `gorm:"column:layer"`
		RawStatus   string    `gorm:"column:raw_status"`
		StateStatus string    `gorm:"column:state_status"`
		Timestamp   time.Time `gorm:"column:timestamp"`
	}
	var incRows []incRow
	h.db.Raw(`
		SELECT i.incident_id, COALESCE(i.device_name, '') AS device_name, COALESCE(i.flag, '') AS flag,
		       COALESCE(i.evidence, '') AS evidence, (i.raw_data IS NOT NULL) AS has_raw,
		       COALESCE(i.confidence, 0) AS confidence, COALESCE(i.layer, 0) AS layer,
		       COALESCE(i.raw_data->>'status', '') AS raw_status, COALESCE(s.status, '') AS state_status,
		       i.timestamp
		FROM incidents i
		LEFT JOIN incident_states s ON s.incident_id = i.incident_id
		ORDER BY i.timestamp DESC
		LIMIT 20
	`).Scan(&incRows)
	for _, inc := range incRows {
		idStr := strconv.Itoa(inc.IncidentID)
		conf := evNormalizeConfidence(inc.Confidence)
		lastTel, hasTel := lastTelemetry[inc.DeviceName]
		fresh := hasTel && time.Since(lastTel) <= evTelemetryFreshness
		resolved := strings.EqualFold(inc.Flag, "RESOLVED") || strings.EqualFold(inc.RawStatus, "RESOLVED") || strings.EqualFold(inc.StateStatus, "RESOLVED")

		quality := 0.0
		if strings.TrimSpace(inc.Evidence) != "" {
			quality += 35
		}
		if inc.HasRaw {
			quality += 15
		}
		if fresh {
			quality += 25
		}
		if conf >= 70 {
			quality += 25
		}

		st := rule6[idStr]
		item := evidenceLogItem{
			TraceID:    "INC-" + idStr,
			IncidentID: idStr,
			Source:     "incidents",
			Host:       inc.DeviceName,
			Quality:    quality,
			Confidence: conf,
			ObservedAt: inc.Timestamp,
			dedupKey:   inc.DeviceName + "|" + strings.ToUpper(inc.Flag),
		}
		switch {
		case resolved && (st == nil || !st.satisfied()):
			item.Status = evStatusConflict
			item.DecisionReason = "RESOLVED tanpa dual-evidence Rule #6 (execution + post-remediation)"
		case conf > 0 && conf < 50:
			item.Status = evStatusNeedMore
			item.DecisionReason = fmt.Sprintf("Confidence %.0f%% di bawah ambang 50%% — butuh bukti tambahan (%s)", conf, inc.Flag)
		case !resolved && !fresh:
			item.Status = evStatusStale
			item.DecisionReason = fmt.Sprintf("Telemetri %s tidak segar (> 15 menit) — anomali: %s", inc.DeviceName, inc.Flag)
		default:
			item.Status = evStatusPass
			if resolved {
				item.DecisionReason = "RESOLVED · Rule #6: " + st.Verdict
			} else {
				item.DecisionReason = "Anomali tervalidasi dengan telemetri segar: " + inc.Flag
			}
		}
		logs = append(logs, item)
	}

	sort.SliceStable(logs, func(i, j int) bool { return logs[i].ObservedAt.After(logs[j].ObservedAt) })

	// Duplicate detection (same host + flag already represented by a newer incident)
	seen := make(map[string]bool)
	for i := range logs {
		if logs[i].dedupKey == "" {
			continue
		}
		if seen[logs[i].dedupKey] && logs[i].Status == evStatusPass {
			logs[i].Status = evStatusDup
			logs[i].DecisionReason = "Duplikat dari insiden lebih baru pada host & flag yang sama"
		}
		seen[logs[i].dedupKey] = true
	}
	if len(logs) > 40 {
		logs = logs[:40]
	}
	for i := range logs {
		logs[i].Age = evHumanAge(logs[i].ObservedAt)
		if logs[i].Host == "" {
			logs[i].Host = "—"
		}
	}

	// Statistics (24h window) & pipeline counters
	counts := map[string]int{}
	window := 0
	var qualitySum, confSum float64
	confN := 0
	for _, l := range logs {
		if time.Since(l.ObservedAt) <= evStatsWindow {
			counts[l.Status]++
			window++
		}
		qualitySum += l.Quality
		if l.Confidence > 0 {
			confSum += l.Confidence
			confN++
		}
	}
	var rawCount int64
	h.db.Raw(`
		SELECT (SELECT COUNT(*) FROM incidents WHERE timestamp >= NOW() - INTERVAL '1 day')
		     + (SELECT COUNT(*) FROM incident_events WHERE created_at >= NOW() - INTERVAL '1 day')
	`).Scan(&rawCount)

	type layerRow struct {
		Layer int `gorm:"column:layer"`
		Cnt   int `gorm:"column:cnt"`
	}
	var layers []layerRow
	h.db.Raw(`SELECT COALESCE(layer, 0) AS layer, COUNT(*) AS cnt FROM incidents WHERE timestamp >= NOW() - INTERVAL '7 days' GROUP BY COALESCE(layer, 0) ORDER BY layer`).Scan(&layers)
	layerTotal := 0
	for _, l := range layers {
		layerTotal += l.Cnt
	}
	osiDist := []string{}
	for _, l := range layers {
		name, ok := osiLayerNames[l.Layer]
		if !ok {
			name = "Unclassified"
		}
		osiDist = append(osiDist, fmt.Sprintf("%s (%s · %d)", name, evPct(l.Cnt, layerTotal), l.Cnt))
	}

	// Readiness (derived strictly from evidence above)
	conflicts := 0
	missing := 0
	for _, l := range logs {
		switch l.Status {
		case evStatusConflict:
			conflicts++
		case evStatusNeedMore, evStatusStale:
			missing++
		}
	}
	readiness := gin.H{"conflicts": conflicts, "missing": missing, "quality": "—", "confidence": "—"}
	avgQuality := 0.0
	if len(logs) > 0 {
		avgQuality = qualitySum / float64(len(logs))
		readiness["quality"] = fmt.Sprintf("%.0f%%", avgQuality)
	}
	if confN > 0 {
		readiness["confidence"] = fmt.Sprintf("%.0f%%", confSum/float64(confN))
	}
	switch {
	case len(logs) == 0:
		readiness["status"], readiness["level"] = "NO EVIDENCE DATA", "none"
		readiness["reason"] = "Belum ada jejak bukti (incidents / incident_events / ai_evidence_quality) yang tercatat."
	case conflicts > 0:
		readiness["status"], readiness["level"] = "BLOCKED — EVIDENCE CONFLICT", "critical"
		readiness["reason"] = fmt.Sprintf("%d bukti konflik (termasuk pelanggaran Rule #6). AI reasoning wajib ditinjau manusia.", conflicts)
	case avgQuality < 70:
		readiness["status"], readiness["level"] = "DEGRADED — HUMAN REVIEW", "warning"
		readiness["reason"] = fmt.Sprintf("Kualitas bukti rata-rata %.0f%% (< 70%%).", avgQuality)
	case missing > 0:
		readiness["status"], readiness["level"] = "READY — PARTIAL EVIDENCE", "warning"
		readiness["reason"] = fmt.Sprintf("%d bukti menunggu data tambahan / telemetri segar.", missing)
	default:
		readiness["status"], readiness["level"] = "READY FOR REASONING", "ok"
		readiness["reason"] = "Seluruh bukti tervalidasi, tanpa konflik Rule #6."
	}

	// Evidence relationship graph (incident → execution → post-remediation)
	graphNodes := []gin.H{}
	graphEdges := []gin.H{}
	added := map[string]bool{}
	if len(logs) > 0 {
		graphNodes = append(graphNodes, gin.H{"id": "root", "label": "Evidence Pipeline\n[VALIDATED]", "color": "#8b5cf6", "shape": "ellipse", "font": gin.H{"color": "#ffffff"}})
	}
	statusColor := map[string]string{evStatusPass: "#22c55e", evStatusConflict: "#ef4444", evStatusStale: "#f59e0b", evStatusNeedMore: "#3b82f6", evStatusDup: "#64748b", evStatusRejected: "#b91c1c"}
	for _, l := range logs {
		if l.IncidentID == "" || added[l.IncidentID] || len(added) >= 6 {
			continue
		}
		added[l.IncidentID] = true
		incNode := "inc_" + l.IncidentID
		label := fmt.Sprintf("#%s", l.IncidentID)
		if l.Host != "—" {
			label = fmt.Sprintf("%s\n(#%s)", l.Host, l.IncidentID)
		}
		graphNodes = append(graphNodes, gin.H{"id": incNode, "label": label, "color": statusColor[l.Status], "shape": "box", "font": gin.H{"color": "#ffffff"}, "incident_id": l.IncidentID})
		graphEdges = append(graphEdges, gin.H{"from": "root", "to": incNode, "label": l.Status, "arrows": "to"})
		if st := rule6[l.IncidentID]; st != nil {
			if st.ExecAt != nil {
				graphNodes = append(graphNodes, gin.H{"id": incNode + "_exec", "label": "EXECUTION\n" + st.ExecAt.Format("15:04:05"), "color": "#0ea5e9", "shape": "ellipse"})
				graphEdges = append(graphEdges, gin.H{"from": incNode, "to": incNode + "_exec", "label": "T_exec", "arrows": "to"})
			}
			if st.PostAt != nil {
				col := "#22c55e"
				if !st.Bound {
					col = "#ef4444"
				}
				parent := incNode
				if st.ExecAt != nil {
					parent = incNode + "_exec"
				}
				graphNodes = append(graphNodes, gin.H{"id": incNode + "_post", "label": "POST-REMEDIATION\n" + st.PostAt.Format("15:04:05"), "color": col, "shape": "ellipse"})
				graphEdges = append(graphEdges, gin.H{"from": parent, "to": incNode + "_post", "label": "T_post ≥ T_exec", "arrows": "to"})
			}
		}
	}

	validated := window - counts[evStatusDup]
	c.JSON(http.StatusOK, gin.H{
		"readiness": readiness,
		"stats": gin.H{
			"window":           "24h",
			"total":            window,
			"validated_pct":    evPct(counts[evStatusPass], window),
			"conflict_pct":     evPct(counts[evStatusConflict], window),
			"need_more_pct":    evPct(counts[evStatusNeedMore]+counts[evStatusStale], window),
			"rejected_pct":     evPct(counts[evStatusRejected], window),
			"osi_distribution": osiDist,
			"pipeline": gin.H{
				"raw":        rawCount,
				"normalized": window,
				"validated":  validated,
				"pass":       counts[evStatusPass],
				"conflict":   counts[evStatusConflict],
				"stale":      counts[evStatusStale],
				"duplicate":  counts[evStatusDup],
				"need_more":  counts[evStatusNeedMore],
				"rejected":   counts[evStatusRejected],
			},
		},
		"collectors": h.loadEvidenceCollectors(),
		"graph":      gin.H{"nodes": graphNodes, "edges": graphEdges},
		"logs":       logs,
	})
}

// GetEvidenceExplorerDetail — GET /api/evidence_explorer/:incident_id
// Returns the evidence timeline and decision audit detail bound to one incident.
func (h *Handler) GetEvidenceExplorerDetail(c *gin.Context) {
	rawID := strings.TrimSpace(c.Param("incident_id"))
	for _, p := range []string{"INC-", "EQ-", "TRC-INC-", "TRC-"} {
		rawID = strings.TrimPrefix(rawID, p)
	}
	incID, err := strconv.Atoi(rawID)
	if err != nil || incID <= 0 {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "incident_id tidak valid"})
		return
	}
	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"status": "error", "message": "Database tidak terhubung"})
		return
	}
	idStr := strconv.Itoa(incID)

	incident := map[string]interface{}{}
	h.db.Raw(`SELECT incident_id, timestamp, device_name, layer, flag, evidence, confidence, rag_status, raw_data->>'status' AS raw_status FROM incidents WHERE incident_id = ?`, incID).Scan(&incident)
	if len(incident) == 0 {
		c.JSON(http.StatusNotFound, gin.H{"status": "error", "message": fmt.Sprintf("Insiden #%d tidak ditemukan", incID)})
		return
	}
	var verificationTime *time.Time
	h.db.Raw(`SELECT verification_time FROM incidents WHERE incident_id = ?`, incID).Scan(&verificationTime)
	incident["verification_time"] = verificationTime

	state := map[string]interface{}{}
	h.db.Raw(`SELECT status, last_updated, resolved_at FROM incident_states WHERE incident_id = ?`, incID).Scan(&state)

	type timelineEntry struct {
		At      time.Time `json:"at"`
		Source  string    `json:"source"`
		Type    string    `json:"type"`
		Summary string    `json:"summary"`
	}
	timeline := []timelineEntry{}
	if ts, ok := incident["timestamp"].(time.Time); ok {
		timeline = append(timeline, timelineEntry{At: ts, Source: "incidents", Type: "DETECTED", Summary: fmt.Sprintf("Anomali %v terdeteksi pada %v", incident["flag"], incident["device_name"])})
	}

	type evRow struct {
		EventType string    `gorm:"column:event_type"`
		Payload   string    `gorm:"column:payload"`
		CreatedAt time.Time `gorm:"column:created_at"`
	}
	var evRows []evRow
	h.db.Raw(`SELECT event_type, COALESCE(payload::text, '{}') AS payload, created_at FROM incident_events WHERE incident_id = ? ORDER BY created_at ASC LIMIT 100`, idStr).Scan(&evRows)
	for _, e := range evRows {
		summary := e.Payload
		var pm map[string]interface{}
		if json.Unmarshal([]byte(e.Payload), &pm) == nil {
			parts := []string{}
			for _, k := range []string{"target_asset", "action", "execution_id", "verification_confidence", "metric_value", "status", "reason"} {
				if v, ok := pm[k]; ok && v != nil && fmt.Sprint(v) != "" {
					parts = append(parts, fmt.Sprintf("%s=%v", k, v))
				}
			}
			if len(parts) > 0 {
				summary = strings.Join(parts, " · ")
			}
		}
		if len(summary) > 240 {
			summary = summary[:240] + "…"
		}
		timeline = append(timeline, timelineEntry{At: e.CreatedAt, Source: "incident_events", Type: e.EventType, Summary: summary})
	}

	type vRow struct {
		Status    string    `gorm:"column:verification_status"`
		Rollback  bool      `gorm:"column:rollback_needed"`
		Latency   int       `gorm:"column:response_latency_ms"`
		CreatedAt time.Time `gorm:"column:created_at"`
	}
	var vRows []vRow
	h.db.Raw(`SELECT COALESCE(verification_status, '') AS verification_status, rollback_needed, COALESCE(response_latency_ms, 0) AS response_latency_ms, created_at FROM verification_logs WHERE incident_id = ? ORDER BY created_at ASC LIMIT 50`, incID).Scan(&vRows)
	for _, v := range vRows {
		timeline = append(timeline, timelineEntry{At: v.CreatedAt, Source: "verification_logs", Type: "VERIFICATION_" + strings.ToUpper(v.Status), Summary: fmt.Sprintf("rollback_needed=%t · latency=%dms", v.Rollback, v.Latency)})
	}

	type aRow struct {
		Action    string    `gorm:"column:action_executed"`
		EventID   string    `gorm:"column:event_id"`
		CreatedAt time.Time `gorm:"column:created_at"`
	}
	var aRows []aRow
	h.db.Raw(`SELECT COALESCE(action_executed, '') AS action_executed, event_id, created_at FROM ai_audit_trail WHERE incident_id = ? ORDER BY created_at ASC LIMIT 50`, incID).Scan(&aRows)
	for _, a := range aRows {
		timeline = append(timeline, timelineEntry{At: a.CreatedAt, Source: "ai_audit_trail", Type: a.Action, Summary: "event_id=" + a.EventID})
	}
	sort.SliceStable(timeline, func(i, j int) bool { return timeline[i].At.Before(timeline[j].At) })

	st := h.loadRule6States()[idStr]
	if st == nil {
		st = &rule6State{Verdict: "NO REMEDIATION EVIDENCE"}
	}

	var approvals int64
	h.db.Raw(`SELECT COUNT(*) FROM ai_approval_logs WHERE incident_id = ? AND approval_status = 'APPROVED'`, incID).Scan(&approvals)

	c.JSON(http.StatusOK, gin.H{
		"status":    "success",
		"incident":  incident,
		"state":     state,
		"rule6":     st,
		"approvals": approvals,
		"timeline":  timeline,
	})
}
