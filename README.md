# Charmed Mongos operator

[![Charmhub](https://charmhub.io/mongos/badge.svg)](https://charmhub.io/mongos)
[![Release to 6/edge](https://github.com/canonical/mongos-operator/actions/workflows/release.yaml/badge.svg)](https://github.com/canonical/mongos-operator/actions/workflows/release.yaml)
[![Tests](https://github.com/canonical/mongos-operator/actions/workflows/ci.yaml/badge.svg)](https://github.com/canonical/mongos-operator/actions/workflows/ci.yaml)

## Overview

The Charmed Mongos operator deploys and operates mongos instances on both physical and virtual machines, along with a wide range of cloud and cloud-like environments.

[mongos](https://www.mongodb.com/docs/v6.0/reference/program/mongos/) is a router for connecting client applications to a sharded MongoDB clusters. It is the only way to access a sharded MongoDB cluster from the client perspective.

It acts as a [subordinate charmed oerator](https://juju.is/docs/sdk/charm-taxonomy#heading--subordinate-charms) and is meant to act as a proxy to a sharded MongoDB cluster. To deploy a sharded MongoDB cluster, please see our [Charmed solution for MongoDB](https://charmhub.io/mongodb).

For information about how to deploy, integrate, and manage this charm, see the Official [Charmed Mongos documentation](https://charmhub.io/mongos).

## Get started
The following steps will guide you through briefly creating a client connection to a sharded MongoDB cluster via `mongos`. 

You'll need a Juju environment and a MongoDB application deployed as a sharded cluster. For guidance about setting up your environment, see the [Charmed MongoDB tutorial for sharded clusters](https://charmhub.io/mongodb/docs/t-set-up-sharding).

### Deploy
To deploy a MongoDB sharded cluster with one shard, run:
```
juju deploy mongodb --config role="config-server" config-server
juju deploy mongodb --config role="shard" shard0
```
> For more information about deploying a MongoDB sharded cluster, see the [tutorial](https://charmhub.io/mongodb/docs/t-deploy-sharding)

To deploy mongos and data-integrator, run:

```none
juju deploy mongos
juju deploy data-integrator --config database-name=<name>
```

### Integrate 
When the status of the `mongos` application becomes `idle`, integrate `mongos` with `data-integrator` and with the `mongodb` application running as `config-server`:
```none
juju integrate mongos data-integrator
juju integrate config-server mongos
```

### Access the database
In order to access the integrated database, you will need the `mongos` URI. To retrieve this, run the following command:
```none
juju run data-integrator/leader get-credentials
```

You will find the URI under the field `uris` in the output.
> For more information about accessing the database, see the Charmed MongoDB documentation for [accessing a client database](https://charmhub.io/mongodb/docs/t-integrate-sharding#heading--access-integrated-database).

### Enable TLS
If the sharded MongoDB cluster has TLS enabled, `mongos` must also enable TLS. Enable it by integrating `mongos` with a TLS application:
```none
juju integrate mongos <tls-application>
```
> For more information about TLS in sharded clusters, see the Charmed MongoDB documentation for [enabling security in sharded clusters](https://charmhub.io/mongodb/docs/t-enable-tls-sharding)

### Remove `mongos`
To remove a `mongos` connection to the sharded cluster, run:
```none
juju remove-relation config-server mongos
```
When`mongos` is removed from the sharded cluster, the client is removed as well.

## Learn more
* Learn more about operating MongoDB sharded clusters and replica sets in the [Charmed MongoDB documentation](https://charmhub.io/mongodb)
* Check the charm's [GitHub repository](https://github.com/canonical/mongos-operator)
* Learn more about the `mongos` router in the upstream [`mongos` documentation](https://www.mongodb.com/docs/v6.0/reference/program/mongos/)

## Project and community
Charmed Mongos is an open source project that warmly welcomes community contributions, suggestions, fixes, and constructive feedback.

* Check our [Code of Conduct](https://ubuntu.com/community/ethos/code-of-conduct)
* Raise software issues or feature requests on [GitHub](https://github.com/canonical/mongos-operator/issues)
* Report security issues through [LaunchPad](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File). 
* Meet the community and chat with us on [Matrix](https://matrix.to/#/#charmhub-data-platform:ubuntu.com)
* [Contribute](https://github.com/canonical/mongodb-operator/blob/main/CONTRIBUTING.md) to the code
