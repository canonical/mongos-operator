# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

output "application" {
  description = "Object representing the deployed mongos application."
  value       = juju_application.mongos
}

# Required integration endpoints
output "requires" {
  description = "Map of all \"requires\" endpoints"
  value = {
    client_certificates = {
      name     = juju_application.mongos.name
      endpoint = "client-certificates"
    }
    cluster = {
      name     = juju_application.mongos.name
      endpoint = "cluster"
    }
    etcd = {
      name     = juju_application.mongos.name
      endpoint = "etcd"
    }
    ldap = {
      name     = juju_application.mongos.name
      endpoint = "ldap"
    }
    ldap_certificate_transfer = {
      name     = juju_application.mongos.name
      endpoint = "ldap-certificate-transfer"
    }
    mongos_proxy = {
      name     = juju_application.mongos.name
      endpoint = "mongos_proxy"
    }
    peer_certificates = {
      name     = juju_application.mongos.name
      endpoint = "peer-certificates"
    }
  }
}
