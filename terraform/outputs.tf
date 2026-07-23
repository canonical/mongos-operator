# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

output "application" {
  description = "Object representing the deployed mongos application."
  value       = juju_application.mongos
}

output "offers" {
  description = "Map of all offers exposed by the single charm."
  value       = {}
}

output "provides" {
  description = "Map of all \"provides\" endpoints"
  value       = {}
}

# Required integration endpoints
output "requires" {
  description = "Map of all \"requires\" endpoints"
  value = {
    certificates = {
      kind     = "endpoint"
      name     = juju_application.mongos.name
      endpoint = "certificates"
    }
    cluster = {
      kind     = "endpoint"
      name     = juju_application.mongos.name
      endpoint = "cluster"
    }
    ldap = {
      kind     = "endpoint"
      name     = juju_application.mongos.name
      endpoint = "ldap"
    }
    ldap_certificate_transfer = {
      kind     = "endpoint"
      name     = juju_application.mongos.name
      endpoint = "ldap-certificate-transfer"
    }
    mongos_proxy = {
      kind     = "endpoint"
      name     = juju_application.mongos.name
      endpoint = "mongos_proxy"
    }
  }
}
