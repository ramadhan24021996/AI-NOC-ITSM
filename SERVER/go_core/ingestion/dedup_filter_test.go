package ingestion

import (
	"testing"
	"time"
)

func TestDedupFilter_IsDuplicate(t *testing.T) {
	window := 1 * time.Second
	df := newDedupFilter(window)
	defer close(df.stopped)

	fp := buildFingerprint("site-01", "KASIR-01", "CPU_HIGH", "critical")

	// 1st occurrence: Should NOT be duplicate
	if df.IsDuplicate(fp) {
		t.Errorf("Expected first occurrence of %s to not be duplicate", fp)
	}

	// 2nd occurrence immediately after: Should BE duplicate
	if !df.IsDuplicate(fp) {
		t.Errorf("Expected immediate second occurrence of %s to be marked as duplicate", fp)
	}

	active, suppressed := df.Stats()
	if active != 1 {
		t.Errorf("Expected 1 active fingerprint, got %d", active)
	}
	if suppressed != 1 {
		t.Errorf("Expected 1 total suppressed count, got %d", suppressed)
	}

	// Wait for window to expire
	time.Sleep(1100 * time.Millisecond)

	// 3rd occurrence after window expiration: Should NOT be duplicate
	if df.IsDuplicate(fp) {
		t.Errorf("Expected occurrence after window expiration to not be duplicate")
	}
}

func TestBuildFingerprint(t *testing.T) {
	fp1 := buildFingerprint("site-A", "PC-1", "NET_DROP", "warning")
	fp2 := buildFingerprint("site-A", "PC-1", "NET_DROP", "critical")

	if fp1 == fp2 {
		t.Errorf("Fingerprints with different priorities should not match: %s vs %s", fp1, fp2)
	}
	if fp1 != "site-A|PC-1|NET_DROP|warning" {
		t.Errorf("Unexpected fingerprint format: %s", fp1)
	}
}
