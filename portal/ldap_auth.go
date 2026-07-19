package main

import (
	"fmt"
	"os"
	"strings"

	"github.com/go-ldap/ldap/v3"
)

// ValidateLDAP checks credentials against LDAP/Active Directory.
func ValidateLDAP(username, password string) (role string, ok bool) {
	if username == "" || password == "" {
		return "", false
	}

	ldapURL := os.Getenv("LDAP_URL")
	if ldapURL == "" {
		// Fallback to env variables if LDAP is not configured
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
		fmt.Printf("LDAP connection error: %v\n", err)
		return "", false
	}
	defer l.Close()

	bindDN := os.Getenv("LDAP_BIND_DN")
	bindPassword := os.Getenv("LDAP_BIND_PASSWORD")
	baseDN := os.Getenv("LDAP_BASE_DN")

	if bindDN != "" && bindPassword != "" {
		err = l.Bind(bindDN, bindPassword)
		if err != nil {
			fmt.Printf("LDAP bind error: %v\n", err)
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
		fmt.Printf("LDAP search error or user not found: %v\n", err)
		return "", false
	}

	userDN := sr.Entries[0].DN

	// Bind as the user to verify their password
	err = l.Bind(userDN, password)
	if err != nil {
		fmt.Printf("LDAP user auth failed: %v\n", err)
		return "", false
	}

	// Verify if user is admin
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
