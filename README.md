# Charmed Mongos Documentation

[mongos](https://www.mongodb.com/docs/v6.0/reference/program/mongos/) is a router for connecting client applications to a sharded MongoDB clusters. It is the only way to access a sharded MongoDB cluster from the client perspective. It stores a small cache of data that reflects the state and organisation of a sharded MongoDB cluster, this data is then used to route queries from client applications to the sharded MongoDB cluster.

Applications like mongos must be managed and operated in the production environment. This means that mongos proxy administrators and analysts who run workloads in various infrastructures should be able to automate tasks for repeatable operational work. Technologies such as software operators encapsulate the knowledge, wisdom and expertise of a real-world operations team and codify it into a computer program that helps to operate complex server applications like MongoDB and other databases.

Canonical has developed an open-source operator called Charmed Mongos, which make it easier to operate mongos. The Charmed mongos Virtual Machine (VM) operator deploys and operates mongos on physical, Virtual Machines (VM) and other wide range of cloud and cloud-like environments, including AWS, Azure, OpenStack and VMWare. It provides straightforward and intelligent integrations with Sharded [Charmed MongoDB](https://charmhub.io/mongodb) deployments and client applications.

Charmed monogs(VM Operator) is an enhanced, open source and fully-compatible drop-in replacement for the MongoDB Community Edition of mongos with advanced mongos enterprise features. It simplifies the deployment, scaling, design and management of mongos in production in a reliable way.

It acts as a [subordinate Charmed Operator](https://discourse.charmhub.io/t/subordinate-applications/1053) and is meant to act as a proxy to a sharded MongoDB cluster. To deploy a sharded MongoDB cluster please see our [Charmed solution for MongoDB](https://charmhub.io/mongodb)



## Software and releases

Charmed Mongos (VM Operator) is an enhanced, open source and fully-compatible drop-in replacement for the mongos router in MongoDB Community Edition with advanced MongoDB enterprise features. This operator uses the [Charmed MongoDB snap package](https://snapcraft.io/charmed-mongodb), which offers more features than the MongoDB Community version, such as backup and restores, monitoring and security features.

To see the Charmed MongoDB features and releases, visit our [Release Notes page](https://github.com/canonical/mongos-operator/releases). Currently the charm supports:
- Automatic User Creation for application users

## Charm version, environment and OS

A charm version is a combination of both the application version and / (slash) the channel, e.g. 6/stable, 6/candidate, 6/edge. The channels are ordered from the most stable to the least stable, candidate, and edge. More risky channels like edge are always implicitly available. So, if the candidate is listed, you can pull the candidate and edge. When stable is listed, all three are available. 

You can deploy the charm in a stand-alone machine or in a cloud and cloud-like environments, including AWS, Azure, OpenStack and VMWare.

The upper portion of this page describes the Operating System (OS) where the charm can run e.g. 6/edge is compatible and should run in a machine with Ubuntu 22.04 OS.


## Security, Bugs and feature request

If you find a bug in this charm or want to request a specific feature, here are the useful links:

* Raise issues or feature requests in [Github](https://github.com/canonical/mongos-operator/issues)

* Security issues in the Charmed MongoDB Operator can be reported through [LaunchPad](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File). Please do not file GitHub issues about security issues.

* Meet the community and chat with us if there are issues and feature requests in our [Matrix Room](https://matrix.to/#/#charmhub-data-platform:ubuntu.com)

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on enhancements to this charm following best practice guidelines, and [CONTRIBUTING.md](https://github.com/canonical/mongos-operator/blob/6/edge/CONTRIBUTING.md) for developer guidance.

## License

The Charmed MongoDB Operator is free software, distributed under the Apache Software License, version 2.0. See [LICENSE](https://github.com/canonical/mongos-operator/blob/6/edge/LICENSE) for more information.

The Charmed Mongos Operator is free software, distributed under the Apache Software License, version 2.0. It [installs/operates/depends on] [MongoDB Community Version](https://github.com/mongodb/mongo), which is licensed under the Server Side Public License (SSPL)

See [LICENSE](https://github.com/canonical/mongos-operator/blob/main/LICENSE) for more information.

## Trademark notice
MongoDB' is a trademark or registered trademark of MongoDB Inc. Other trademarks are property of their respective owners.
