// Package auth menyediakan autentikasi LDAP & JWT untuk portal.
// Dipindahkan dari portal/ldap_auth.go ke package terpisah agar dapat
// diimpor dan diuji secara independen.
package auth

import (
	"fmt"
	"os"
	"strings"

	"github.com/go-ldap/ldap/v3"
)

// ValidateLDAP memeriksa kredensial terhadap LDAP/Active Directory.
// Mengembalikan role ("admin"/"operator") dan status sukses.
func ValidateLDAP(username, password string) (role string, ok bool) {
	if username == "" || password == "" {
		return "", false
	}

	ldapURL := os.Getenv("LDAP_URL")
	if ldapURL == "" {
		// Fallback ke env variables jika LDAP tidak dikonfigurasi
		adminUsers := os.Getenv("LDAP_ADMIN_USERS")
		adminPass := os.Getenv("LDAP_ADMIN_PASSWORD")
		operatorPass := os.Getenv("LDAP_OPERATOR_PASSWORD")

		if adminUsers != "" && adminPass != "" && password == adminPass {
			for _, u := range strings.Split(adminUsers, ",") {
				if strings.EqualFold(strings.TrimSpace(u), username) {
					return "admin", true
				}
			}
		}
		if operatorPass != "" && password == operatorPass {
			return "operator", true
		}
		return "", false
	}

	l, err := ldap.DialURL(ldapURL)
	if err != nil {
		fmt.Printf("[AUTH] LDAP connection error: %v\n", err)
		return "", false
	}
	defer l.Close()

	bindDN := os.Getenv("LDAP_BIND_DN")
	bindPassword := os.Getenv("LDAP_BIND_PASSWORD")
	baseDN := os.Getenv("LDAP_BASE_DN")

	if bindDN != "" && bindPassword != "" {
		if err = l.Bind(bindDN, bindPassword); err != nil {
			fmt.Printf("[AUTH] LDAP bind error: %v\n", err)
			return "", false
		}
	}

	searchRequest := ldap.NewSearchRequest(
		baseDN,
		ldap.ScopeWholeSubtree, ldap.NeverDerefAliases, 0, 0, false,
		fmt.Sprintf("(&(objectClass=organizationalPerson)(uid=%s))", ldap.EscapeFilter(username)),
		[]string{"dn"},
		nil,
	)

	sr, err := l.Search(searchRequest)
	if err != nil || len(sr.Entries) != 1 {
		fmt.Printf("[AUTH] LDAP search error or user not found: %v\n", err)
		return "", false
	}

	userDN := sr.Entries[0].DN
	if err = l.Bind(userDN, password); err != nil {
		fmt.Printf("[AUTH] LDAP user auth failed: %v\n", err)
		return "", false
	}

	// Periksa apakah user adalah admin
	adminUsers := os.Getenv("LDAP_ADMIN_USERS")
	if adminUsers != "" {
		for _, u := range strings.Split(adminUsers, ",") {
			if strings.EqualFold(strings.TrimSpace(u), username) {
				return "admin", true
			}
		}
	}

	return "operator", true
}
