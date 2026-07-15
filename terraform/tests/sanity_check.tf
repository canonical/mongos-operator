module "mongos" {
  source     = "../"
  app_name   = var.mongos_name
  channel    = "8/edge"
  model_uuid = var.model_uuid
}

resource "juju_application" "data-integrator" {
  charm {
    name    = "data-integrator"
    channel = "latest/stable"
  }
  model_uuid = var.model_uuid
}


resource "juju_integration" "mongos_client" {
  model_uuid = module.mongos.application.model_uuid

  application {
    name     = juju_application.data-integrator.name
    endpoint = "mongos"
  }
  application {
    name     = module.mongos.requires["mongos_proxy"].name
    endpoint = module.mongos.requires["mongos_proxy"].endpoint
  }
  depends_on = [
    juju_application.data-integrator,
    module.mongos
  ]
}
