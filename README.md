<img src="https://neuralberta.tech/images/event/natHACKs/nathanGlow.png" height="250">

# natKit

This is a collection of tools created to help jumpstart users on working with BCI hardware. By providing ways to connect, process, and visulize data from various peices of hardware.


## Installation

### Requirements

- [Docker](https://docs.docker.com/get-docker/)
- [Python](https://www.python.org/downloads/) 3.9 or above
- [virtualenv](https://docs.python.org/3/library/venv.html)


### From Source

Clone the repository:
```sh
git clone --recurse-submodules https://github.com/neuralbertatech/natKit
cd natKit
```

Create a virtual environment to install the dependencies:
```sh
python -m venv <Environment-Name>  # For example  $ python -m venv .venv
```

Activate the virtual environment and install the dependencies (Platform-Specific):
#### MacOS and Linux
```sh
source ./<Environment-Name>/bin/activate  # source ./.venv/bin/activate
pip install -r requirements.txt
```

### Windows (Powershell)
```sh
./<Environment-Name>/Scripts/Activate.ps1
pip install -r requirements.txt
```

### Development Docker stack

Start Docker Desktop and wait for its Linux container engine to report that it
is running. Then, from the repository root, build the repo-owned images and
start the complete development stack:

```sh
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

This builds the natKit frontend, backend, bridge, and ML control plane from the
local source tree while pulling third-party infrastructure images such as Kafka,
Mosquitto, and NTP. Open the development UI at <http://localhost:8080>.

To leave the stack running in the background, add `--detach`:

```sh
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build --detach
```

If the repository was cloned without `--recurse-submodules`, initialize its
submodules before building:

```sh
git submodule update --init --recursive
```

See [Docker Compose development troubleshooting](docs/docker-compose-dev-troubleshooting.md)
for common Docker Desktop, Windows line-ending, and optional ML worker issues.

## Getting Started

Now to get started go to the bin/ folder and run some scripts, for example:
```sh
python ./bin/muse-2-producer.py &
python ./bin/stream-visulizer-gui.py
```

## Additional Configuration

### Docker Server

If your docker server is running on a remote machine (or a different port on the same machine), you can configure the connection parameters using the environment variables:
- `NATKIT_SERVER` for the server address
- `NATKIT_SERVER_PORT` for the server port

For example if you had the server running on a machine located at `192.168.0.12` on port `1234` you would set the environment variables with:
```sh
export NATKIT_SERVER="192.168.0.12"
export NATKIT_SERVER_PORT="1234"
```
(for windows)
```sh
$env:NATKIT_SERVER="192.168.0.12"
$env:NATKIT_SERVER_PORT="1234"
```

## Troubleshooting

### Execution Policy (Windows)

Run the following command from Powershell (with admin privaledges)
```sh
Set-ExecutionPolicy -ExecutionPolicy Unrestricted
```
