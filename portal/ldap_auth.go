package main

// ldap_auth.go — Delegation wrapper ke portal/pkg/auth package.
// Fungsi ValidateLDAP sekarang didefinisikan di pkg/auth/ldap.go.
// File ini dipertahankan untuk kompatibilitas backward dengan kode lain
// yang menggunakan ValidateLDAP dari package main.

import portalAuth "go_incident_analysis/portal/pkg/auth"

// ValidateLDAP mendelegasikan autentikasi ke pkg/auth.ValidateLDAP.
// Menjaga backward compatibility agar semua call site tidak perlu diubah.
func ValidateLDAP(username, password string) (role string, ok bool) {
	return portalAuth.ValidateLDAP(username, password)
}
