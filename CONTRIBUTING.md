# Contributing

To make contributions to this charm, you'll need a working [development setup](https://juju.is/docs/sdk/dev-setup).

## Developing
Install `tox` and `poetry`
```shell
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install tox
pipx install poetry
```

You can create an environment for development:

```shell
poetry install
```

## Testing

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

```shell
tox run -e format        # update your code according to linting rules
tox run -e lint          # code style
tox run -e static        # static type checking
tox run -e unit          # unit tests
tox run -e integration   # integration tests
tox                      # runs 'format', 'lint', 'static', and 'unit' environments
```

## Build the charm

Build the charm in this git repository using:

```shell
tox run -e build
```

<!-- You may want to include any contribution/style guidelines in this document>
